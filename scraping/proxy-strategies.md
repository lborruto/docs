# Proxy Strategies for Web Scraping

The proxy model is dictated by what the target's anti-bot layer binds trust to: the IP, a session, or a clearance cookie. Pick the model from the target's behaviour, not from the proxy provider's marketing. This article covers the three models, how to tell which one a target needs, and the operational rules that keep a residential pool healthy and cheap.

## Three Models

| | Rotating per request | Sticky per session | Sticky per cookie set |
|--|---------------------|--------------------|-----------------------|
| **Exit IP** | New IP every request | One IP for the life of a warm session (1–2 h) | One IP for the life of one clearance cookie set (25–30 min) |
| **Trust anchor** | None -- the exit IP's reputation is judged on every request | Session cookies that accumulate trust through navigation | A challenge cookie bound to the IP that solved it |
| **Typical protection** | Reputation-scored edges without an IP-bound cookie | Bot managers that score session history (Akamai-style) | Challenge pages whose clearance cookie is IP-bound (Cloudflare) |
| **Failure mode of the wrong model** | Sticky pins you to one flagged IP and blocks cascade | Rotating throws away the trust the session earned | Rotating 403s on every fetch; a single fixed IP hits per-IP rate limits |
| **Cost model** | Per GB (~$1–3/GB residential) | Per GB, plus provider sticky fee if any | Per GB |

The provider is the same in all three cases -- a rotating residential gateway with a sticky-session modifier. Only the way session IDs are assigned changes.

### 1. Rotating per request

Use when the edge scores the exit IP on each request and no cookie is bound to the IP. Each request draws a fresh IP, so a flagged exit only costs one request:

```python
from curl_cffi.requests import Session as CurlSession

session = CurlSession(
    impersonate="chrome",
    proxy="http://user:pass@gate.provider.com:port",
)
resp = session.get("https://target.example.com/search?q=test")
```

The rule that matters here: **a 403 is almost always the exit IP, not the cookie.** Keep the cookie set and retry it on a fresh IP; retire it only after it fails on several distinct IPs. Marking a cookie set sick on its first 403 burns healthy cookies, drains the warm pool, and turns a transient bad IP into a mint storm.

Measured against a reputation-scored Cloudflare Enterprise edge, with one cookie set and 18 requests each: rotating passed 15/18 and both failures recovered on the next IP; sticky passed 3/18. Rotating averages out flagged exits; sticky pins you to one.

### 2. Sticky per session

Use when the bot manager scores session history. A session that has done a couple of legitimate-looking page loads (homepage, then a category page) carries `bm_sv`/`ak_bmsc`-style cookies that dominate the score afterwards -- as long as the IP does not change under it.

```python
import uuid

def sticky_proxy(base_user, password, host, port, sessttl_min):
    """Random session id -> the provider keeps the same exit IP for sessttl_min minutes."""
    sid = uuid.uuid4().hex[:12]
    return f"http://{base_user};sessid.{sid};sessttl.{sessttl_min}:{password}@{host}:{port}"

proxy = sticky_proxy("user", "pw", "gate.provider.com", 823, sessttl_min=120)
session = CurlSession(impersonate="chrome", proxy=proxy)
session.get("https://target.example.com/")          # warm-up 1: homepage cookies
session.get("https://target.example.com/category")  # warm-up 2: session trust
# ... the session then serves its request budget (about 12 requests) before retirement
```

Operating rules:

- **Align the sticky window with the pool's session TTL.** If the pool retires a session after 2 hours, ask the provider for a 2-hour sticky window. A sticky window shorter than the session TTL rotates the IP under a live cookie jar, which is the failure the model is meant to avoid. Verify the provider actually honours the value you request; some gateways silently cap it.
- **Retire by request count as well as age.** An unvalidated session gets blocked around its 19th–20th request; retiring at about 12 leaves margin for multi-request legs and concurrent workers. Add ±20 % jitter on the TTL so a fleet restart does not expire every session at once.
- **A sticky IP that returned a 403 is not reused within the hour.** Per-IP scores do not recover immediately, and hammering a flagged IP worsens the cluster signal for the same fingerprint + ASN.
- IP reputation is paid once, at session mint, and amortised over the session's requests. That is why a cheap pool with a 30–50 % cold-mint success rate still delivers 95 %+ sustained throughput behind a warm pool: failed mints are retried by the maintainer and never reach the caller.

### 3. Sticky per cookie set

Use when the challenge cookie only validates from the IP that solved it. The invariant is **solve IP == fetch IP**: the challenge solver must run through a sticky session, that session's proxy URL is stored next to the cookie set, and every fetch reusing those cookies goes through the same URL.

```python
import time

def mint_cookie_set(solver, target_url):
    proxy = sticky_proxy("user", "pw", "gate.provider.com", 823, sessttl_min=30)
    cookies = solver.solve(target_url, proxy=proxy)     # solved ON the sticky exit
    return {"cookies": cookies, "proxy": proxy, "expires_at": time.time() + 25 * 60}

def fetch(cookie_set, url):
    session = CurlSession(impersonate="chrome", proxy=cookie_set["proxy"])  # SAME exit
    for name, value in cookie_set["cookies"].items():
        session.cookies.set(name, value, domain=".target.example.com")
    session.headers["User-Agent"] = cookie_set["cookies"]["user_agent"]
    return session.get(url)
```

Why not the two obvious shortcuts:

- **Solve on the server's own IP, fetch through the rotating proxy** -- every fetch 403s, whatever the TLS impersonation, because the cookie is bound to the solver's IP.
- **Solve and fetch on one fixed IP with no proxy** -- passes validation but trips the per-IP throttle: a handful of rapid requests returns 429 (the cookie stays valid, the IP is throttled) and the penalty persists for minutes, with no fallback. One IP cannot carry a scraper's whole traffic.

A fresh sticky session per cookie set gives both properties at once: the cookie validates (same IP) and the traffic is spread across as many IPs as there are live cookie sets (no per-IP throttle). Set the sticky window to the cookie's lifetime (a 30-minute clearance cookie wants a 30-minute sticky window) and retire both together.

#### The solver must really use the proxy

Headless challenge solvers (FlareSolverr-compatible services such as Byparr) accept a proxy, but not always where the API suggests. Some ignore the `proxy` field in the request body and only honour per-request headers:

```python
def solver_proxy_headers(proxy_url):
    proto_user, host = proxy_url.split("@", 1)
    creds, password = proto_user.rsplit(":", 1)
    proto, _, user = creds.rpartition("://")
    return {
        "X-Proxy-Server": f"{proto}://{host}",
        "X-Proxy-Username": user,      # keeps ";sessid.X;sessttl.N" intact
        "X-Proxy-Password": password,
    }
```

Verify the egress once: have the solver load an IP-echo page through the proxy and compare with the IP a direct fetch through the same sticky URL reports. If they differ, the cookie will never validate and every 403 will look like a fingerprint problem when it is an IP mismatch.

Solver retries: rotate to a fresh sticky exit on each attempt (a proxy gateway error from one exit recovers on another), give the client a timeout above the solver's own internal maximum, and bound the attempts. Do not hold a fleet-wide mint lock for the whole solve when solves take 15–60 s -- serialised minting is what turns a bad hour into an outage.

## Which Model Does a Target Need?

| Observation | Model |
|-------------|-------|
| Fresh cookies fetched from a different IP than the one that solved them return 403, while the same cookies on the solving IP return 200 | Sticky per cookie set |
| A cold session gets challenged or blocked but the same session passes after a homepage + category warm-up, and keeps passing while the IP holds | Sticky per session |
| Blocks look random, clear on an immediate retry, and correlate with the exit IP rather than with the cookies | Rotating per request |
| The same IP returns 429 after a burst although the cookies are valid | Add IP diversity: more sticky sessions or rotate, never a single fixed IP |

Test the first row explicitly before building anything: solve once, replay through the proxy, replay through the solver's IP. Edges change their binding rules over time; a model that was right for a target six months ago may be the wrong one today.

## Sticky Session Syntax

Rotating residential gateways expose stickiness through the username or the port. Syntax varies by provider:

- **Username modifiers** -- `user;sessid.X;sessttl.N` (N in minutes, semicolon-delimited). The gateway pins the exit IP to the session id for N minutes. Check the maximum honoured on the port you use; some gateways accept values well above the documented default (120 minutes has been verified on a gateway documenting 30).
- **Session parameters in the username** -- `user-session-RANDOM-sessionduration-N`, one sticky IP per session id.
- **Per-port stickiness** -- a dedicated port range where each port is one sticky IP for its lifetime.

Use a random session id for within-process stickiness; use a deterministic one (for example a hash of an account id) when several processes must share one IP for the same identity.

## Pool Hygiene

Whichever sticky model applies, the sessions live in a Redis-backed warm pool that a background maintainer keeps at a target size. The rules that keep it healthy:

- **Checkout drains stale entries in a bounded loop.** A checkout that pops one stale entry and gives up returns nothing under load: stale sessions accumulate at the head of the list while fresh ones sit at the tail. Loop up to the list length at call time and return the first fresh entry.
- **TTL jitter** (±20 %) so a boot burst does not expire the whole pool at once.
- **Sick marking on real blocks only** (403 with valid cookies after retries, captcha pages), never on timeouts or proxy gateway errors, which are the exit's fault. Garbage-collect sick entries after an hour.
- **Mint lock with a bounded wait** (`SET key 1 NX EX 30`, wait a few seconds, release in `finally`), so N workers seeing an empty pool at boot do not mint N copies.
- **A health check that exercises the real path.** A solver container that answers its HTTP health endpoint can still be unable to start a browser; check something that only works when solves work.

## Rate Limiting

With rotating proxies there is no per-IP state to manage; jitter the behaviour instead, and escalate on blocks (three blocks within two minutes → a 120-second backoff):

```python
import random, time

time.sleep(random.uniform(1.0, 3.0))
```

With sticky sessions, limit per session rather than per IP:

```python
class RateLimiter:
    def __init__(self, min_delay=0.5, max_delay=1.5):
        self._min, self._max, self._last = min_delay, max_delay, {}

    def wait(self, key):
        earliest = self._last.get(key, 0) + random.uniform(self._min, self._max)
        time.sleep(max(0, earliest - time.time()))
        self._last[key] = time.time()
```

Read 429 and 403 differently: 429 means the IP is throttled and the cookies are fine (spread traffic over more sticky sessions); 403 with valid cookies means the exit or the cookie is rejected (retry on another exit, then retire the cookie set).

## Bandwidth and Cost

Residential proxies bill wire bytes, and the response is already compressed on the wire. The decompressed body length that HTTP clients report overstates the billed volume by roughly 10×, so never estimate spend from it. Compression is not a lever; **page count is**:

- Ask for the largest page size the target allows -- twice the listings per page is roughly 15 % fewer bytes per listing and half the requests.
- Sweep incrementally with a recency sort and a cursor plus a small margin (one day when dates are day-granular); reserve exhaustive sweeps (price buckets, deep pagination) for one-time backfills.
- Abort warm-up downloads early: session cookies arrive in the response headers, so stream the warm-up page and stop after ~64 KB (about 150 KB on the wire instead of 1–2 MB).
- Skip a synthetic warm-up step when a real request is waiting and can serve as the second navigation.

Order of magnitude: an hourly sweep of ~330 pages is ~70 MB per run, ~1.7 GB per day at $1/GB; dropping redundant bucket passes and doubling the page size cut it by about 60 %.

## Where You Test From Matters

Gateways hand out different exit cohorts depending on the source IP that authenticates. The same code, proxy URL and client version measured 1/10 successes from a home ISP address and 97 % sustained success from a datacenter host. Validate success rates from the host that will run the scraper; from a laptop, limit yourself to direct (non-proxied) fetches for code and TLS sanity, unit tests with mocked HTTP, and smoke runs that only confirm the code path executes.

## Evaluating a Provider

Benchmark before integrating: throwaway scripts run from the deployment host, measuring cold-mint success (how often a warm-up produces a usable session) and sustained success (warm-session requests over an hour). Providers cluster into tiers by mint success on the strongest bot managers -- cheap tiers ($1–2/GB) around 30–50 %, mid tiers ($2–5/GB) 50–80 %, premium tiers ($4–10/GB, KYC and minimum spend) 80–95 %. Behind a warm pool the cheap tier reaches the same sustained rate as the premium one, because failed mints are absorbed by the maintainer; premium is worth paying for only when there is no pool or cold mints are the bottleneck. Keep the candidate out of the codebase until the decision is made, and delete any credentials left on test hosts.

## The French ISP Proxy Problem

If you need French IPs, be aware of a structural limitation:

- **All French ISP proxies are Orange** -- every provider delivers IPs on AS5511/AS3215. Free (AS12322), SFR (AS15557), Bouygues (AS5410) don't participate in IP-leasing markets.
- **0 % residential classification** on IP2Location -- the IPs are technically ISP IPs but classified as hosting/proxy.
- **Single-ASN correlation** -- anti-bot systems detect that all your IPs share the same ASN; blocks cascade after roughly 100–150 requests.
- **Confirmed by providers** -- one French provider's own words: "en FR, c'est impossible d'avoir des IPs catégorisées ISP" on IP2Location.

Rotating residential proxies avoid this entirely: each request is a different IP from a different ASN.

### Does IP Classification Matter?

| Anti-Bot System | IP Intelligence Source | Uses IP2Location? |
|----------------|----------------------|-------------------|
| **Akamai Bot Manager** | Own proprietary (~30 % global traffic) | No |
| **Cloudflare Enterprise** | Own internal (~20 % global traffic) | No |
| **DataDome** | Own ML + likely IP2Location (~25–30 % of score) | Probably |

Akamai and Cloudflare have enough traffic to build their own IP databases. Third-party classification is irrelevant for them -- but the single-ASN problem still applies.

## Scraper API Alternative

All proxy management (rotation, stickiness, rate limiting, TLS impersonation, challenge solving) can be offloaded to a scraper API:

```python
import requests

response = requests.get("http://api.scrape.do/", params={
    "url": "https://target.example.com/page",
    "token": SCRAPEDO_TOKEN,
    "geoCode": "FR",
}, timeout=30)
```

| | Self-managed | Scraper API |
|--|-------------|-------------|
| **Cost** | ~$6–30/mo (proxies) | ~$29–99/mo |
| **Infrastructure** | Proxy config, pools, rate limiting, challenge solver | One env var |
| **Control** | Full | None (black box) |
| **Reliability** | 95 %+ (depends on tuning) | ~100 % (provider handles bypass) |
| **Vendor lock-in** | None | Single point of failure |
