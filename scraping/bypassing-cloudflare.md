# Bypassing Cloudflare with curl_cffi and Cookie Management

How to scrape Cloudflare Enterprise-protected pages using Chrome TLS impersonation, cookie reuse, and a stealth browser for challenge solving -- without running a headless browser per request.

## What Cloudflare Detects

Cloudflare Enterprise layers multiple defenses:

- **TLS fingerprinting** -- matches the TLS handshake against known browser profiles (same principle as Akamai)
- **JS challenges** -- "Just a moment..." interstitial pages that run JavaScript to verify browser capabilities
- **Turnstile challenges** -- interactive CAPTCHA-like widgets
- **`cf_clearance` cookies** -- once a challenge is solved, Cloudflare issues cookies that bypass future challenges for ~25 minutes
- **HTTP 403/429 responses** -- hard blocks when cookies are invalid or traffic is flagged

The key difference from Akamai: Cloudflare's cookie-based challenge system means you can solve **one** challenge and reuse the cookies across many requests.

## The Approach

```
1. Keep a Redis-backed warm pool of N cookie sets (default 10)
2. On each request, check one out, inject into a curl_cffi session, send
3. On 200 → return the cookie set to the pool (request_count++)
4. On CF 403/429 → mark the cookie set sick, rotate proxy IP, retry
5. A background maintainer mints replacements via Byparr, GCs sick entries
```

One sick cookie set never blocks the rest of the fleet, and proactive retirement (TTL `CM_POOL_COOKIE_TTL_S=1500` with +-20% jitter; max `CM_POOL_MAX_REQUESTS_PER_COOKIE=50`) keeps `__cf_bm` from hitting its 30-min Cloudflare ceiling mid-request.

## TLS Impersonation + Cookie Injection

Same `curl_cffi` + Chrome impersonation as for Akamai (see [Bypassing Akamai](bypassing-akamai.md)). The addition is injecting Cloudflare cookies before each request:

```python
from curl_cffi.requests import Session as CurlSession

session = CurlSession(
    impersonate="chrome",  # alias resolves to the latest Chrome target
    timeout=20,
    proxy="http://user:pass@gate.provider.com:port",
)

# Inject Cloudflare cookies obtained from a previous challenge solve
for name in ('cf_clearance', '__cf_bm', '_cfuvid'):
    if cookies.get(name):
        session.cookies.set(name, cookies[name], domain='.target.com')

# The User-Agent MUST match the one used during the challenge solve
if cookies.get('user_agent'):
    session.headers['User-Agent'] = cookies['user_agent']

resp = session.get("https://target.example.com/page")
```

Important: `__cf_bm` is the critical cookie -- Cloudflare rejects requests without it. It is **not IP-bound**, so cookies solved from one IP (Byparr's server IP) work across different proxy IPs (the rotating DataImpulse pool).

## Solving Challenges with Byparr

[Byparr](https://github.com/ThePhaseless/Byparr) runs a [Camoufox](https://github.com/nichochar/camoufox) stealth browser (Firefox-based, anti-fingerprint) that solves Cloudflare JS challenges and Turnstile.

### Docker Setup

```yaml
byparr:
  image: ghcr.io/thephaseless/byparr:latest
  shm_size: 2gb
  deploy:
    resources:
      limits:
        memory: 2G
      reservations:
        memory: 512M
  environment:
    LOG_LEVEL: info
    LANG: fr_FR
    TZ: Europe/Paris
```

### Cookie Solve (Preferred)

Returns cookies you can inject into curl_cffi for subsequent requests:

```python
import requests

def solve_for_cookies(url, byparr_url="http://byparr:8191"):
    resp = requests.post(f"{byparr_url}/v1", json={
        "cmd": "request.get",
        "url": url,
        "max_timeout": 60,
    })
    solution = resp.json()['solution']
    cookies = {c['name']: c['value'] for c in solution['cookies']}
    cookies['user_agent'] = solution['userAgent']
    return cookies
```

### HTML Solve (Fallback)

Returns the fully rendered page HTML when cookie injection doesn't work:

```python
def solve_challenge(url, byparr_url="http://byparr:8191"):
    resp = requests.post(f"{byparr_url}/v1", json={
        "cmd": "request.get",
        "url": url,
        "max_timeout": 30,
    })
    return resp.json()['solution']['response']  # raw HTML
```

Cookie solve is preferred because one solve provides cookies for hundreds of subsequent curl_cffi requests. HTML solve is a last resort.

The solve runs from the container's own IP (no proxy needed) because `__cf_bm` cookies are not IP-bound.

## Cookie Caching: From One-Cookie to a Warm Pool

Solving a challenge takes 15-35 seconds. You don't want to do this on every request, and you don't want a single shared cookie either: one 403 wipes it for every worker until the next solve.

The fix is a Redis-backed **warm pool** of N parallel cookie sets. Workers check one out per request, return it on success, mark it sick on a CF 403. A background maintainer keeps the pool topped up. One sick cookie no longer impacts the rest of the fleet.

### Redis layout

```
cm:pool:warm          LIST    # cookie ids ready for use
cm:pool:sick          SET     # cookie ids that died, pending GC
cm:pool:cookie:{cid}  HASH    # cf_clearance, __cf_bm, _cfuvid, user_agent,
                              # created_at, expires_at, request_count, status
cm:pool:mint_lock     STRING  # NX-locked across the fleet to serialize mints
```

### Pool primitives

```python
checkout()                       -> meta dict | None   # LPOP warm, skip-if-stale
return_cookie(cid, success=...)                        # RPUSH warm or mark sick
mark_sick(cid, reason)                                 # LREM warm + SADD sick
apply_cookies(session, meta)                           # inject into curl_cffi session
mint_one(respect_ceiling=False) -> cid | None          # Byparr solve + RPUSH warm
gc_sick()                       -> int                 # delete end-of-life entries
```

Each cookie set carries a `request_count` (retired at `CM_POOL_MAX_REQUESTS_PER_COOKIE=50`) and `expires_at` (TTL `CM_POOL_COOKIE_TTL_S=1500` with +-20% jitter, so a boot burst doesn't synchronously expire). `_is_stale` checks both on every checkout.

### Background maintainer

No external cron. Inside gunicorn workers, a gevent greenlet started at boot wakes every `CM_POOL_MAINT_INTERVAL_S=60` and:

1. mints until `LLEN(cm:pool:warm) >= CM_POOL_TARGET_SIZE` (default 10);
2. runs `gc_sick()` to delete retired entries immediately and sick entries after 1 hour.

Mint operations are serialized across the fleet by `cm:pool:mint_lock` (`SET NX EX 60`), so N workers all seeing an empty pool at boot don't mint N copies in parallel.

Cron and batch scripts don't import `app.py`, so they have no greenlet. They call `cm_pool_maintainer.prewarm_pool()` once at startup to synchronously fill the pool before scrapes begin; on a pool miss mid-run they inline-mint via `cm_pool.mint_one()`.

### Configuration knobs

```
CM_POOL_ENABLED=true                  # master kill-switch
CM_POOL_TARGET_SIZE=10                # warm cookies the maintainer keeps
CM_POOL_MAX_REQUESTS_PER_COOKIE=50    # retire-on-count
CM_POOL_COOKIE_TTL_S=1500             # 25 min, with +-20% jitter
CM_POOL_MAINT_INTERVAL_S=60           # maintainer loop cadence
CM_POOL_MINT_TIMEOUT_S=60             # hard cap on a single Byparr solve
```

The old single-cookie `CM_COOKIE_TTL=1500` knob is still present for legacy code paths but the pool's own TTL is what matters now.

## Challenge Detection

Check for Cloudflare challenge markers in the response:

```python
def is_cloudflare_challenge(html):
    snippet = html[:2000]
    return any(marker in snippet for marker in (
        "Just a moment",
        "challenge-platform",
        "cf_challenge",
        "cf-chl",
        "Checking your browser",
        "window._cf_chl",
    ))
```

## Putting It Together

The production flow (`scraper.cardmarket_session._cm_request`) checks a cookie set out of the pool, retries with proxy-IP rotation on 403, and falls back to a Byparr HTML-direct solve only when retries are exhausted:

```python
from scraper import cm_pool
from scraper.cardmarket_session import create_cm_session
from scraper.flaresolverr import solve_challenge

def scrape(url, *, cm_cookie_block: bool, cm_solve_on_block: bool,
           cm_max_attempts: int = 2):
    # Pool checkout. On empty pool, cron/batch (cm_cookie_block=True)
    # inline-mints via Byparr; frontend goes bare to preserve the 6s deadline.
    meta = cm_pool.checkout() if config.CM_POOL_ENABLED else None
    if meta is None and cm_cookie_block:
        if cm_pool.mint_one():
            meta = cm_pool.checkout()

    first_403_handled = False
    for attempt in range(cm_max_attempts):
        # A fresh session per attempt = a fresh DataImpulse IP (rotating proxy).
        sess = create_cm_session(timeout=20)
        if meta is not None:
            cm_pool.apply_cookies(sess, meta)  # sets cookies + UA, domain=.cardmarket.com
        try:
            resp = sess.get(url)
        finally:
            sess.close()

        if resp.status_code == 200:
            if meta is not None:
                cm_pool.return_cookie(meta['cid'], success=True)
            return resp.text

        if resp.status_code in (403, 429):
            if attempt < cm_max_attempts - 1:
                if not first_403_handled and meta is not None and cm_cookie_block:
                    # Cron/batch first 403: maybe the cookie is stale.
                    # Mark it sick, grab a fresh one from the pool.
                    cm_pool.mark_sick(meta['cid'], 'cf_403_first')
                    meta = cm_pool.checkout() or (
                        cm_pool.checkout() if cm_pool.mint_one() else None)
                    first_403_handled = True
                # else: keep cookies, just rotate IP via a new session next loop.
                time.sleep(0.5)
                continue
            break  # retries exhausted — fall through to fallback

    # Final attempt failed with 403/429.
    if meta is not None:
        cm_pool.mark_sick(meta['cid'], 'cf_403_exhausted')

    # Byparr HTML-direct fallback — cron/batch only, ~10s round-trip.
    if cm_solve_on_block:
        html = solve_challenge(url, timeout=35)
        if html and not is_cloudflare_challenge(html):
            return html

    raise CMBlockedError('cf_403')
```

Two behavior knobs control the cron-vs-frontend split:

- **`cm_cookie_block`** — `True` for cron/batch: inline-mint on pool miss, swap cookies on first 403. `False` for frontend: go bare on pool miss, never swap cookies (rotate IP only), so the 6s deadline holds.
- **`cm_solve_on_block`** — `True` for cron/batch: after retries exhausted, ask Byparr to fetch the URL directly via headless browser. `False` for frontend: raise `CMBlockedError` immediately.

The same pool primitives also guard a body-level challenge (HTTP 200 with a "Just a moment..." page): on detection `_cm_get` does one fresh pool checkout + retry, marks the prior cookie sick if the retry still sees a challenge, then falls back to a Byparr HTML-direct solve. See `scraper.cardmarket_session._cm_get`.

Asymmetry to keep in mind:

- **Cron / batch** (`cm_cookie_block=True`, `cm_max_attempts=4`): allowed to mark the cookie sick on the first 403, swap to a fresh pool entry, and inline-mint via Byparr when the pool is empty.
- **Frontend** (`cm_cookie_block=False`, `cm_max_attempts=2`): never marks the cookie sick on intermediate 403s — only rotates the proxy IP via a fresh `create_cm_session()`. The cookie is only marked sick if all retries are exhausted. On a pool miss the frontend goes bare (no inline mint, no Byparr) to preserve the 6s scrape deadline.

There is no separate `trigger_background_solve()` API: background replenishment is owned by the gevent maintainer greenlet (`cm_pool_maintainer.iteration()`), which refills toward `CM_POOL_TARGET_SIZE` every `CM_POOL_MAINT_INTERVAL_S` and GCs sick entries. Workers never block on a Byparr solve except via `mint_one()` on a deliberate cron-path pool miss.

### `CMNetworkError` vs `CMBlockedError`

`cardmarket_session.py` raises two distinct exception classes that callers (and the metrics layer) must NOT collapse into a single "scrape failed" bucket:

- **`CMNetworkError`** (`cardmarket_session.py:92`) — proxy connection reset, DNS failure, TCP timeout. Raised at line 255-256 from inside the request loop. The cookie is NEVER marked sick on these — the failure has nothing to do with the cookie's validity, and burning the pool on transient proxy hiccups would empty it during any minor proxy provider blip.
- **`CMBlockedError`** (`cardmarket_session.py:87`) — Cloudflare returned 403, an HTTP 5xx that survived retries, or a body-level challenge that Byparr couldn't solve. Raised at lines 325 / 352 / 414 / 454. Cookies are marked sick on these (subject to the `cm_cookie_block` asymmetry above).

Callers that catch one and not the other risk either (a) leaking proxy failures into the cookie-sick count and prematurely draining the pool, or (b) ignoring Cloudflare-driven blocks because they look like network noise. The split is load-bearing — preserve it when adding new error paths.

## Results

- **Cookie solve frequency**: ~once per 25 minutes
- **Per-request latency**: 1-2s (with cached cookies)
- **Cold start latency**: 15-35s (challenge solve)
- **Cost**: Byparr is self-hosted and free (~512MB RAM)
- **No headless browser per request** -- Camoufox only runs for the initial solve
