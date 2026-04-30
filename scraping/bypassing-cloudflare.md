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
1. Solve the Cloudflare challenge once (via stealth browser, ~15-35s)
2. Extract cf_clearance + __cf_bm cookies
3. Inject those cookies into curl_cffi requests
4. All subsequent requests bypass the challenge (~1-2s each)
5. When cookies expire (~25 min) or get a 403, re-solve
```

## TLS Impersonation + Cookie Injection

Same `curl_cffi` + a pinned Chrome impersonation as for Akamai (see [Bypassing Akamai](bypassing-akamai.md)). The addition is injecting Cloudflare cookies before each request:

```python
from curl_cffi.requests import Session as CurlSession

session = CurlSession(
    impersonate="chrome145",
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

Important: `__cf_bm` is the critical cookie -- Cloudflare rejects requests without it. It is **not IP-bound**, so cookies solved from one IP work across different proxy IPs.

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

## Cookie Caching

Solving a challenge takes 15-35 seconds. You don't want to do this on every request. Cache the cookies and reuse them until they expire:

```python
_cached_cookies = None
_cached_at = 0
COOKIE_TTL = 1500  # 25 minutes

def get_or_solve_cookies(target_url):
    global _cached_cookies, _cached_at
    if _cached_cookies and time.time() - _cached_at < COOKIE_TTL:
        return _cached_cookies
    _cached_cookies = solve_for_cookies(target_url)
    _cached_at = time.time()
    return _cached_cookies
```

For multi-process setups, store cookies in Redis instead of a global variable so all workers share the same solve:

```python
def store_cookies(redis_client, cookies):
    redis_client.hset("cf_cookies", mapping=cookies)
    redis_client.expire("cf_cookies", 1500)

def load_cookies(redis_client):
    data = redis_client.hgetall("cf_cookies")
    return data if data and data.get('__cf_bm') else None
```

### Tip: Proactive Refresh

Re-solve at ~20 minutes (before the 25-min expiry) to avoid ever hitting a 403 from expired cookies.

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

```python
def scrape(url):
    cookies = get_or_solve_cookies(url)

    session = CurlSession(impersonate="chrome145", timeout=20, proxy=proxy_url)
    for name in ('cf_clearance', '__cf_bm', '_cfuvid'):
        if cookies.get(name):
            session.cookies.set(name, cookies[name], domain='.target.com')
    if cookies.get('user_agent'):
        session.headers['User-Agent'] = cookies['user_agent']

    resp = session.get(url)

    if resp.status_code in (403, 429):
        # Cookies expired or invalid -- re-solve and retry once
        cookies = solve_for_cookies(url)
        store_cookies(redis_client, cookies)
        # ... rebuild session with new cookies and retry
        return None

    if resp.status_code == 200 and is_cloudflare_challenge(resp.text):
        # Got a 200 but it's a challenge page -- try HTML solve
        return solve_challenge(url)

    return resp.text
```

## Results

- **Cookie solve frequency**: ~once per 25 minutes
- **Per-request latency**: 1-2s (with cached cookies)
- **Cold start latency**: 15-35s (challenge solve)
- **Cost**: Byparr is self-hosted and free (~512MB RAM)
- **No headless browser per request** -- Camoufox only runs for the initial solve
