# Bypassing Cloudflare with curl_cffi and Cookie Management

How to scrape Cloudflare Enterprise-protected pages using browser TLS impersonation, a pool of solved cookie sets, and a stealth browser for challenge solving -- without running a headless browser per request.

## What Cloudflare Detects

Cloudflare Enterprise layers multiple defenses:

- **TLS fingerprinting** -- matches the TLS handshake against known browser profiles (same principle as Akamai)
- **JS challenges** -- "Just a moment..." interstitial pages that run JavaScript to verify browser capabilities
- **Turnstile challenges** -- interactive CAPTCHA-like widgets
- **Clearance cookies** -- once a challenge is solved, Cloudflare issues cookies (`cf_clearance`, `__cf_bm`, `_cfuvid`) that bypass future challenges for ~25 minutes
- **HTTP 403/429 responses** -- hard blocks when cookies are invalid or traffic is flagged

The key difference from Akamai: Cloudflare's cookie-based challenge system means you can solve **one** challenge and reuse the cookies across many requests. The catch is what those cookies are bound to.

## What the Cookies Are Bound To

Treat a solved cookie set as bound to **the IP that solved it and the browser that solved it**:

- **IP** -- a cookie set minted on one IP and replayed through a different (or rotating) IP returns 403 on every fetch, whatever the impersonation. Diagnose it in three fetches: same cookies on the solving IP → 200; through a rotating proxy → 403; a real browser through the proxy → 200 (the browser solves and uses the cookies on one IP in one shot). The IP mismatch is the only variable left.
- **TLS fingerprint** -- a Firefox User-Agent (the solver's) over a Chrome TLS handshake is the mismatch class Cloudflare rejects. The fetch must impersonate the same browser family, ideally the same major version, as the solver.

Both bindings can be switched on by the edge at any time; a target that tolerated replay across IPs for months can stop overnight. Test the bindings explicitly before blaming fingerprints or the proxy provider.

## The Approach

```
1. Keep a Redis-backed warm pool of N cookie sets (8–10), each solved through
   its OWN sticky proxy session and stored with that session's proxy URL
2. On each request, check one out, inject into a curl_cffi session that egresses
   through the cookie set's sticky proxy and impersonates the solver's browser
3. On 200 → return the cookie set to the pool (request_count++)
4. On 403/429 → retry the same cookie set; if every attempt fails, mark it sick
   and let the next request check out another cookie set (its own exit IP)
5. A background maintainer mints replacements via the solver, GCs sick entries
```

One sick cookie set never blocks the rest of the fleet, and proactive retirement (25-minute TTL with ±20% jitter; 50 requests per cookie set) keeps `__cf_bm` from hitting its 30-minute Cloudflare ceiling mid-request. A fresh sticky exit per cookie set spreads traffic over as many IPs as there are live cookie sets, which keeps every single IP under Cloudflare's per-IP throttle (a handful of rapid requests from one IP returns 429 for minutes).

## TLS Impersonation + Cookie Injection

The fetch reuses `curl_cffi` like the Akamai path (see [Bypassing Akamai](bypassing-akamai.md)), with three additions: the sticky proxy the cookies were solved on, an impersonation target derived from the solver's User-Agent, and the cookies themselves:

```python
import re
from curl_cffi.requests import Session as CurlSession
from curl_cffi import requests as _cffi

FALLBACK_TARGET = "firefox135"   # any Firefox target the installed curl_cffi ships

def impersonate_for(solver_ua):
    """firefox<major> when the installed curl_cffi has that exact target."""
    m = re.search(r"Firefox/(\d+)", solver_ua or "")
    if m and f"firefox{m.group(1)}" in _cffi.BrowserType.__members__:
        return f"firefox{m.group(1)}"
    return FALLBACK_TARGET

def make_session(cookie_set, timeout=20):
    session = CurlSession(
        impersonate=impersonate_for(cookie_set["user_agent"]),
        timeout=timeout,
        proxy=cookie_set["proxy_session"],          # the exit that solved the challenge
    )
    for name in ("cf_clearance", "__cf_bm", "_cfuvid"):
        if cookie_set.get(name):
            session.cookies.set(name, cookie_set[name], domain=".target.example.com")
    session.headers["User-Agent"] = cookie_set["user_agent"]   # MUST match the solve
    return session
```

`__cf_bm` is the critical cookie -- Cloudflare rejects requests without it. `cf_clearance` only appears when the target actually served an interstitial challenge; a target on a lighter ruleset may hand out `__cf_bm` + `_cfuvid` alone, and those still need the same IP and fingerprint story.

## Solving Challenges with a Stealth Browser

[Byparr](https://github.com/ThePhaseless/Byparr) (a FlareSolverr-compatible API) runs a [Camoufox](https://github.com/nichochar/camoufox) stealth browser (Firefox-based, anti-fingerprint) that solves Cloudflare JS challenges and Turnstile.

### Docker setup

```yaml
byparr:
  image: ghcr.io/thephaseless/byparr:latest
  restart: unless-stopped
  init: true
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
  healthcheck:
    test:
      - CMD-SHELL
      - >-
        find /tmp -maxdepth 1 -name '.X*-lock' -mmin +60 -delete;
        find /tmp/.X11-unix -type s -mmin +60 -delete 2>/dev/null;
        [ "$$(find /tmp -maxdepth 1 -name '.X*-lock' | wc -l)" -lt 200 ]
        && curl -sf "http://127.0.0.1:$${PORT:-8191}/health" > /dev/null
    interval: 60s
    timeout: 15s
    retries: 3
    start_period: 30s
```

The health check matters more than it looks. Every solve opens a virtual X display, and an aborted solve (client timeout, killed browser) leaks its `/tmp/.X{n}-lock`. The display range is finite (~300); once exhausted the container cannot start **any** browser, every mint fails, the pool drains -- and the image's own HTTP health ping keeps reporting "healthy" because it never starts a browser. Sweeping locks older than an hour every minute makes the container self-heal; failing the check at 200 fresh locks makes a genuine stall visible. Note that a plain container restart does not clear `/tmp`; the sweep has to run inside the container.

Give the solver its own outbound network: it needs internet egress and to be reachable by the workers, nothing else.

### Cookie solve (preferred), through the sticky proxy

Returns cookies you inject into curl_cffi for subsequent requests. The proxy goes in **per-request headers**: Byparr reads `X-Proxy-Server` / `X-Proxy-Username` / `X-Proxy-Password` and ignores the FlareSolverr-style `proxy` field in the body (verified by having the solver load an IP-echo page: body field → the container's own IP, headers → the proxy IP). Send both for FlareSolverr compatibility.

```python
import requests

def proxy_headers(proxy_url):
    proto_user, host = proxy_url.split("@", 1)
    creds, password = proto_user.rsplit(":", 1)
    proto, _, user = creds.rpartition("://")
    return {"X-Proxy-Server": f"{proto}://{host}",
            "X-Proxy-Username": user,            # keeps ";sessid.X;sessttl.N" intact
            "X-Proxy-Password": password}

def solve_for_cookies(url, new_sticky_proxy, solver_url="http://byparr:8191",
                      attempts=3, client_timeout=90):
    """One fresh sticky exit per attempt; returns the cookies AND the proxy that solved them."""
    for _ in range(attempts):
        proxy = new_sticky_proxy()                                   # sessttl ~30 min
        resp = requests.post(f"{solver_url}/v1",
                             json={"cmd": "request.get", "url": url, "max_timeout": 60,
                                   "proxy": {"url": proxy}},
                             headers=proxy_headers(proxy),
                             timeout=client_timeout)                 # ABOVE max_timeout
        data = resp.json()
        if data.get("status") != "ok" or not data["solution"].get("cookies"):
            continue                                                 # bad exit → next attempt, new exit
        cookies = {c["name"]: c["value"] for c in data["solution"]["cookies"]}
        cookies["user_agent"] = data["solution"]["userAgent"]
        cookies["proxy_session"] = proxy
        return cookies
    return None
```

Three details carry the reliability:

- **A fresh sticky exit per attempt.** The dominant solve failure is the proxy exit itself (a gateway error mid-solve, a throttled IP). Re-solving on the same exit reproduces it; the next attempt on a new exit recovers.
- **Client timeout above the solver's `max_timeout`** (90 s vs 60 s), so the solver's own answer -- success or failure -- wins the race instead of a client-side read timeout that leaves a browser running.
- **Bounded attempts** (3), then fail the mint and let the maintainer try again later.

Solve a cheap, always-challenged page of the target (a category listing), never the pages you scrape.

### HTML solve (fallback)

Returns the fully rendered page when cookie injection cannot be used -- a last resort for batch paths, ~10–20 s per page, no cookie reuse:

```python
def solve_challenge(url, solver_url="http://byparr:8191", attempts=3):
    for _ in range(attempts):
        resp = requests.post(f"{solver_url}/v1",
                             json={"cmd": "request.get", "url": url, "max_timeout": 30},
                             timeout=45)
        data = resp.json()
        if data.get("status") == "ok" and data["solution"].get("response"):
            return data["solution"]["response"]      # raw HTML
    return None
```

Cookie solve is preferred because one solve provides cookies for dozens of subsequent curl_cffi requests. Solving takes 15–35 s; the challenge itself is most of it, and the solver opens a fresh browser context per call, so there is no clearance reuse inside the solver -- the pool is where reuse lives.

## Cookie Caching: From One Cookie to a Warm Pool

You don't want to solve on every request, and you don't want a single shared cookie either: one 403 wipes it for every worker until the next solve.

The fix is a Redis-backed **warm pool** of N parallel cookie sets. Workers check one out per request, return it on success, mark it sick when it is exhausted. A background maintainer keeps the pool topped up. One sick cookie set no longer impacts the rest of the fleet.

### Redis layout

```
pool:warm          LIST    # cookie ids ready for use
pool:sick          SET     # cookie ids that died, pending GC
pool:cookie:{cid}  HASH    # cf_clearance, __cf_bm, _cfuvid, user_agent, proxy_session,
                           # created_at, expires_at, request_count, status
pool:mint_lock     STRING  # NX-locked across the fleet to serialize mints
```

### Pool primitives

```
checkout()                       -> meta dict | None   # drain stale entries, return the first fresh one
return_cookie(cid, success=...)                        # RPUSH warm, or retire when exhausted / expired
mark_sick(cid, reason)                                 # LREM warm + SADD sick
apply_cookies(session, meta)                           # inject cookies + UA into a curl_cffi session
mint_one(respect_ceiling=False) -> cid | None          # solver + sticky exit, RPUSH warm
gc_sick()                       -> int                 # delete end-of-life entries
```

Each cookie set carries a `request_count` (retired at 50) and `expires_at` (TTL 1500 s with ±20% jitter, so a boot burst doesn't synchronously expire). Checkout scans from the head of the warm list, moves every stale entry it meets to the sick set, and returns the first fresh one; the scan is bounded by the list length at call time. A checkout that pops one stale entry and gives up returns nothing under load while fresh cookies sit at the tail -- that failure looks exactly like "Cloudflare blocks everything".

### Background maintainer

Inside the worker processes, a background task started at boot wakes every 20–60 s and:

1. mints until `LLEN(pool:warm) >= TARGET_SIZE` (8–10);
2. runs `gc_sick()` to delete retired entries immediately and sick entries after 1 hour.

Mint operations are serialized across the fleet by `pool:mint_lock` (`SET NX EX 60`), so N workers all seeing an empty pool at boot don't mint N copies in parallel. Do not hold the lock for longer than one solve.

Cron and batch scripts have no background task. They call `prewarm_pool()` once at startup to synchronously fill the pool before scrapes begin; on a pool miss mid-run they inline-mint via `mint_one()`.

### Configuration knobs

```
POOL_ENABLED=true                 # master kill-switch
POOL_TARGET_SIZE=8                # warm cookie sets the maintainer keeps
POOL_MAX_REQUESTS_PER_COOKIE=50   # retire-on-count
POOL_COOKIE_TTL_S=1500            # 25 min, with ±20% jitter
POOL_PROXY_SESSTTL_MIN=30         # sticky window per cookie set — at least the cookie TTL
POOL_MAINT_INTERVAL_S=20          # maintainer loop cadence
SOLVE_MAX_ATTEMPTS=3              # solver attempts per mint, one fresh exit each
SOLVE_CLIENT_TIMEOUT_S=90         # above the solver's max_timeout (60)
```

## Challenge Detection

Check for Cloudflare challenge markers in the response body -- a challenge can arrive as an HTTP 200:

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

The request flow checks a cookie set out of the pool, sends through that cookie set's sticky proxy with the solver's browser impersonated, retries on 403/429 without penalising the cookie set until the last attempt, and falls back to an HTML-direct solve only on batch paths:

```python
def fetch(url, *, batch: bool, max_attempts: int):
    # Pool checkout. On an empty pool, batch paths inline-mint; interactive
    # paths go bare to preserve their response-time budget.
    meta = pool.checkout()
    if meta is None and batch and pool.mint_one():
        meta = pool.checkout()

    for attempt in range(max_attempts):
        sess = make_session(meta) if meta else bare_session()
        try:
            try:
                resp = sess.get(url)
            except NETWORK_ERRORS:
                # Proxy reset, DNS, TCP timeout: the cookie set is fine.
                if attempt < max_attempts - 1:
                    time.sleep(0.5 + random.uniform(-0.1, 0.2))
                    continue
                if meta:
                    pool.return_cookie(meta["cid"], success=True)
                raise NetworkError()
        finally:
            sess.close()

        if resp.status_code == 200:
            if meta:
                pool.return_cookie(meta["cid"], success=True)
            return resp.text
        if resp.status_code == 404:
            if meta:
                pool.return_cookie(meta["cid"], success=True)
            return None
        if resp.status_code in (403, 429):
            if attempt < max_attempts - 1:
                time.sleep(0.5 + random.uniform(-0.1, 0.2))   # same cookies, same exit, retry
                continue
            break                                             # exhausted → fall through
        if resp.status_code >= 500:
            if attempt < max_attempts - 1:
                time.sleep(0.5 + random.uniform(-0.1, 0.2))
                continue
            if meta:
                pool.return_cookie(meta["cid"], success=True)  # a 5xx is not the cookie's fault
            raise BlockedError(f"http_{resp.status_code}")

    if meta:
        pool.mark_sick(meta["cid"], "cf_403_exhausted")
    if batch:
        html = solve_challenge(url)
        if html and not is_cloudflare_challenge(html):
            return html
    raise BlockedError("cf_403")
```

Two behaviours split by caller type:

- **Batch / cron** (`max_attempts=4`): inline-mints on a pool miss, and after retries are exhausted asks the solver to fetch the URL directly through the headless browser.
- **Interactive** (`max_attempts=2`): goes bare on a pool miss (no inline mint, no solver) so the page's response-time budget holds, and raises immediately when retries are exhausted.

Neither path marks a cookie set sick on an intermediate 403. Retiring a cookie set on its first 403 was the classic self-inflicted outage: it burns healthy cookie sets, drains the pool and turns a transient block into a serialised re-mint storm behind a 15–35 s solver. With one sticky exit per cookie set, the retry is a plain retry; the exit only changes when the next request checks out another cookie set.

The same primitives guard a body-level challenge (HTTP 200 with a "Just a moment..." page): on detection, do one fresh pool checkout and retry, mark the prior cookie set sick if the retry still sees a challenge, then fall back to the HTML-direct solve on batch paths.

### Network errors vs blocks

Raise two distinct exception classes and never collapse them into one "scrape failed" bucket:

- **Network error** -- proxy connection reset, DNS failure, TCP timeout. The cookie set is NEVER marked sick on these: the failure has nothing to do with the cookies, and burning the pool on transient proxy hiccups empties it during any minor provider blip.
- **Blocked** -- Cloudflare returned 403/429 on every attempt, an HTTP 5xx survived retries, or a body-level challenge the solver could not clear. The cookie set is retired.

Callers that catch one and not the other either leak proxy failures into the sick count and drain the pool prematurely, or ignore Cloudflare-driven blocks because they look like network noise. The split is load-bearing -- preserve it when adding error paths.

## Results

- **Solve frequency**: one per cookie set, every ~25 minutes; 8 live cookie sets ≈ one solve every 3 minutes fleet-wide
- **Per-request latency**: ~1 s with pooled cookies
- **Cold start latency**: 15–35 s (challenge solve), paid by the maintainer, not by callers
- **Cost**: the solver is self-hosted (2 GB RAM ceiling, ~512 MB typical); proxy spend is the residential per-GB rate on small pages
- **No headless browser per request** -- the stealth browser only runs for mints
