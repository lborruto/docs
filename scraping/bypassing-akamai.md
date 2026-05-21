# Bypassing Akamai Bot Manager with curl_cffi

How to scrape Akamai-protected pages using Chrome TLS impersonation — without a headless browser.

## What Akamai Detects

Akamai Bot Manager scores requests on a 0–100 scale starting with the very first request. The score combines signals from three gates: protocol-level fingerprint, IP/session reputation, and request pattern. Documentation often presents these as co-equal "all three must pass" requirements, but in practice **session trust dominates once you have a warm cookie jar** — a session that has built up an `ak_bmsc`/`bm_sv` history through legitimate-looking navigation rides through subsequent requests largely independent of the IP's baseline reputation. The warm-pool architecture below is what makes a cheap-residential proxy viable on Premier targets.

### Gate 1 — Protocol-level fingerprint

- **JA3/JA4 TLS fingerprinting** — cipher suite ordering, TLS extensions (including post-quantum X25519MLKEM768 on recent Chrome), and ALPN sequence. Akamai matches the handshake against a database of known-good browser profiles.
- **HTTP/2 fingerprint (Akamai format)** — concatenates `SETTINGS_LIST | WINDOW_UPDATE | PRIORITY_FRAMES | PSEUDO_HEADER_ORDER`. Each browser version has a stable string; any drift is a mismatch.
- **Header order + Sec-CH-UA consistency** — the UA major version must match the highest `Sec-CH-UA` brand version; `Sec-CH-UA-Mobile: ?1` must imply mobile UA; Firefox/Safari UAs must NOT send Sec-CH-UA at all (those headers are Chromium-only).
- **Sec-Fetch-\* triad** — `Sec-Fetch-Site: none` for a typed URL, `same-origin`/`same-site`/`cross-site` for subsequent navigations.

### Gate 2 — IP / session reputation

Akamai operates Client Reputation, a global IP scoring system shared across all Akamai customers, but **session-level state (`ak_bmsc`, `bm_sv`, `_abck`) accumulates trust on top of the IP baseline** and dominates the score for any request that already has a warm cookie jar.

- IP scoring still matters for the very first request from an unwarmed session: cheap residential pools carry shared abuse history that puts the first hit at a sub-zero baseline.
- Once Akamai has minted `ak_bmsc`/`bm_sv` for a session and that session has done a few legitimate-looking page loads, subsequent requests are scored predominantly on the session, not the IP.
- This is why the warm-pool architecture (see below) turns a $1/GB residential proxy into 95%+ sustained success — you pay the IP-reputation cost once per session mint instead of once per request.
- Reputation decays over a ~30-day rolling window; IPs burned today stay flagged for weeks, but session-warming pulls future requests out of that penalty range.

### Gate 3 — Request pattern (velocity + clustering)

Akamai aggregates request counts across multiple keys, **not per-IP alone**:

- ASN (autonomous system number) — all proxy provider exits share one ASN
- TLS fingerprint hash — even with rotating IPs, the same JA3 from the same ASN clusters
- URL template — 300 hits on `/sch/i.html?...&LH_Sold=1` in 5 minutes from one ASN trips the cluster threshold even if every individual IP is different.
- Time-of-day — 24/7 patterns or daily-heartbeat patterns at the same UTC minute get flagged.

Rotating IPs per request **does not defeat cluster detection** because the cluster key is multi-dimensional.

## Real-World Success Rate Bands

For a pure-HTTP scraper (curl_cffi + residential proxies, no JS execution):

| Path type | Expected sustained rate |
|---|---|
| Bot Manager Standard, no `_abck` validation | 85–95% with good config |
| Bot Manager Premier with `_abck` validation, no sensor forgery | 50–80% |
| Content Protector enabled (Akamai's 2024 scraper-specific product) | 30–60% |

Any documentation claiming "<5% block rate" is either outdated, run against unprotected paths, or measured before Akamai's recent rule updates. eBay-tier targets running Premier + Content Protector are at the harder end of the range.

The dominant variable for sustained success rate is **session warmth**, not IP pool quality or fingerprint freshness. A perfect TLS impersonation with a fresh, unwarmed session through a clean residential pool still bottoms out at 30–60% on a Premier target. The same fingerprint through the cheapest $1/GB residential, but riding a warm `ak_bmsc`/`bm_sv` from a homepage→category warmup, sustains 95%+ on eBay-tier traffic — measured live in our prod fleet over the last 48h. Proxy quality matters for the cold mint; the pool architecture matters for everything after.

## curl_cffi: Chrome TLS Impersonation

[curl_cffi](https://github.com/lexiforest/curl_cffi) is a Python binding for libcurl that impersonates real browsers at the TLS level. Setting `impersonate="chrome146"` (or the current latest) reproduces that Chrome version's exact:

- TLS cipher suite ordering, extensions, GREASE values, signature algorithms
- HTTP/2 SETTINGS frame values, WINDOW_UPDATE cadence, pseudo-header order
- ALPN negotiation sequence
- Sec-CH-UA, User-Agent, Accept, Accept-Encoding matching the impersonated version

```python
from curl_cffi.requests import Session as CurlSession
from curl_cffi.const import CurlOpt
import random

_ACCEPT_LANGUAGES = [
    "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "fr-FR,fr;q=0.9,en-US;q=0.5,en;q=0.3",
    "fr-FR,fr;q=0.9",
]

session = CurlSession(
    impersonate="chrome",   # alias resolves to the latest installed target
    timeout=15,
    allow_redirects=True,
    headers={"Accept-Language": random.choice(_ACCEPT_LANGUAGES)},
    proxy="http://user:pass@gate.provider.com:port",
    curl_options={
        CurlOpt.TCP_KEEPALIVE: 1,
        CurlOpt.TCP_KEEPIDLE: 60,
        CurlOpt.TCP_KEEPINTVL: 30,
        CurlOpt.DNS_CACHE_TIMEOUT: 300,
        CurlOpt.MAXCONNECTS: 10,
        CurlOpt.PIPEWAIT: 1,            # HTTP/2 multiplexing
        CurlOpt.CONNECTTIMEOUT_MS: 3000,
        CurlOpt.IPRESOLVE: 1,           # IPv4-only — skip AAAA + Happy Eyeballs
    },
)

resp = session.get("https://target.example.com/search?q=test")
```

### Picking the impersonate target

The `chrome` alias auto-tracks the latest target curl_cffi ships. As of `curl_cffi==0.15.1b1` that resolves to `chrome148`. Pinning the explicit version (`impersonate="chrome148"`) means your scraper's wire image only changes when you upgrade the library — convenient for stability but easy to forget.

**The "best" impersonate target rotates over time.** Akamai's per-tenant ML auto-tunes its scoring; an impersonate that passed 100% last week may drop to 20% next week. Specific patterns observed in the field:

- For commerce sites whose real-user base is desktop Chrome on Windows/macOS, `chrome` consistently outperforms `firefox` / `chrome_android` / `safari_ios`. Akamai's prior probability is "this endpoint should be served from Chrome desktop", so a Chrome fingerprint matches the legitimate baseline.
- Mobile impersonations (`chrome_android`, `safari_ios`) work well on mobile-API endpoints but get flagged on desktop-oriented endpoints.
- `firefox` often works well on tenants where Firefox usage is significant in the user base, but worse on French/UK e-commerce sites where Firefox share is single-digit percent.

For sustained operation, run a small **daily probe** (20–30 requests across candidate impersonates against a cheap public path) and pin the day's winner. The list of candidates worth probing:

```python
CANDIDATES = [
    "chrome",          # alias — latest stable Chrome
    "chrome131",       # one version back, sometimes survives longer
    "firefox",         # for tenants with significant Firefox user base
    "chrome_android",  # mobile path
    "safari_ios",      # mobile path
]
```

In CollectValue prod we've run that probe and the outcome (2026-05-12 A/B) was that single-target `chrome` outperforms any rotation we tested against eBay.fr. The pool is currently pinned via `EBAY_IMPERSONATE_POOL=('chrome',)` with weighted-sampling support left in for future re-tuning (`EBAY_IMPERSONATE_PRIMARY_WEIGHTS`, empty by default). The probe pattern above is still the right method to use when the success rate drifts — we just settled on a single-target outcome this round.

### What NOT to set manually

curl_cffi's `impersonate=` already handles `User-Agent`, `Sec-CH-UA`, `Sec-CH-UA-Mobile`, `Sec-CH-UA-Platform`, `Accept`, and `Accept-Encoding` for the impersonated browser. Overriding these breaks the fingerprint:

- Wrong `Sec-CH-UA` version vs the UA's major version → strong bot signal.
- Adding `Sec-CH-UA-Wow64: ?0` with `Sec-CH-UA-Platform: "macOS"` → contradictory (Wow64 is Windows-only).
- Adding high-entropy hints (`Sec-CH-UA-Full-Version-List`, `Sec-CH-UA-Arch`, `Sec-CH-UA-Bitness`, `Sec-CH-UA-Platform-Version`) with mismatched values → worse than not sending them at all.

The general rule: if curl_cffi doesn't set a header for a given impersonate, do not invent values for it. Real Firefox doesn't send `Sec-CH-UA`; if you add it to a Firefox-impersonated request, you create the mismatch you were trying to avoid.

The only header consistently worth setting manually is `Accept-Language`, because curl_cffi doesn't localize this.

## IP Reputation: A Cost You Pay At Session Mint, Not Per Request

For a target with strong protocol-level scoring, IP pool quality determines how expensive each **session mint** is — i.e. how often the homepage→category warmup gets blocked before producing a usable `ak_bmsc`/`bm_sv`. It does **not** determine the steady-state success rate of warm-session requests, which is dominated by session trust (see below).

In practice, with a warm pool maintaining N pre-warmed sessions:

- The IP reputation cost is paid once per mint, then amortized across the 15–25 requests that session services before retirement.
- A cheap residential pool with a 50% mint success rate still ends up at 95%+ sustained throughput, because failed mints are retried at the maintainer layer and never reach the caller.
- Without a pool, every request pays the cold-mint penalty. There IP reputation matters directly and the cheapest tiers do bottom out at the rates below.

### Provider tiers — relevant for cold-mint cost, not sustained rate

- **Cheapest tier ($1–2/GB):** rough pool with significant shared abuse history. ~30–50% mint success on Akamai Premier; viable when a warm pool absorbs the misses. DataImpulse, IPRoyal residential, SOAX standard.
- **Mid tier ($2–5/GB):** noticeably cleaner. Decodo, IPRoyal standard, SOAX premium reach 50–80% mint success. Less retry pressure on the maintainer.
- **Premium tier ($4–10/GB):** Bright Data, Oxylabs, NodeMaven specifically curate against pre-flagged IPs. 80–95% mint success but mandatory KYC and minimum spends. Worth it if you don't have a pool, or if your scrape volume makes cold mints the bottleneck.

### Sticky-session lifetime

When the target serves an `ak_bmsc` or `bm_sv` cookie, reusing the same IP for multiple requests lets that cookie's session state accumulate trust. 10–30 minutes per sticky IP is the typical sweet spot — long enough to amortize cookie warming, short enough to limit damage if Akamai escalates scoring mid-session.

In CollectValue prod we run longer: `EBAY_POOL_PROXY_SESSTTL_MIN=120` (2h) paired with `EBAY_POOL_SESSION_TTL_S=7200`, probe-verified that DataImpulse honors `sessttl.120` on port 823. The longer window lets a single warmed cookie jar service 15–25 requests (the per-session retire bound) without the IP rotating mid-life. The `±20%` TTL jitter (`cm_pool.py`/`akamai_pool.py`) handles the synchronous-expiration risk that would otherwise come with 2h sessions.

Most rotating-residential providers offer sticky modes:

- **Per-request session ID** (e.g. `user-USERNAME-session-RANDOM-sessionduration-N` in the username) — fully programmable, one sticky IP per session ID.
- **Per-port stickiness** (e.g. dedicated ports `10001–49999` on Decodo) — each port = one sticky IP for its full lifetime.
- **Sessid + sessttl modifiers in the username** (dataimpulse format: `USER__cr.fr;sessid.X;sessttl.30`) — sessid pins the IP for sessttl minutes, defaults 30, max 120.

### IP cleanup heuristic

When a sticky IP returns a 403, don't reuse it within the next hour. Akamai's per-IP score doesn't immediately recover, and burning more requests through a flagged IP only worsens the cluster signal for the same fingerprint+ASN combination.

## Request Pattern: The Velocity + Cluster Gate

The cluster-detection gate is the most counterintuitive of the three. Even with per-request IP rotation, 300 requests in 5 minutes from one proxy ASN, with the same TLS fingerprint, against the same URL template, trips Akamai's rate policy because the rate is keyed on `(ASN, fingerprint-hash, URL-template, time-window)`, not on the IP alone.

### Pacing

For a ~1,000-requests-per-day scraper:

- **Serial is better than parallel.** Two concurrent workers triggers per-IP burst rules even though throughput-wise you don't need parallelism at this volume.
- **Inter-request jitter of 10–60 seconds.** Uniform timing without jitter is detected as botnet-pattern.
- **Spread across the target's business day** (12–18 hours). 24/7 continuous activity is itself a signal.
- **Don't fire all daily traffic in one 5-minute burst.** Even at 1,000/day, a single nightly batch concentrates the cluster signal far more than the same volume spread over hours.

```python
import random
import time

# Inter-request delay — random jitter prevents pattern detection
time.sleep(random.uniform(10.0, 60.0))
```

### Retry pacing

When a request returns 403, immediately retrying against the same target with a new IP looks like a bot's retry loop. Sleep 30–120s (random) before the retry. This both lets the proxy pool rotate and avoids the burst-retry pattern.

### Cookie discard on 403

If the session received an `ak_bmsc` or `bm_sv` cookie before the 403, Akamai has flagged that session as Strict. Continued requests on the same session — even from a new IP — will fail. Discard the cookie jar after any 403 and start fresh.

## Pool Architecture: Sustained Multi-Worker Operation

The naive "fresh session per scrape" pattern pays the homepage→category warmup cost on every request and produces fingerprint+cookie trails that get flagged quickly. For sustained operation across a fleet — multiple gunicorn workers, cron jobs, batch backfills — a pre-warmed session pool is the right primitive.

### The model

Maintain a Redis-backed pool of N pre-warmed sessions. Each session carries:

- A sticky proxy session (10–30 min lifetime)
- An Akamai cookie jar (`ak_bmsc`, `bm_sv`, sometimes `_abck`) populated by a homepage→category warmup chain
- A per-session request counter — retire at 15–25 requests to bound per-session blast radius
- A **jittered** TTL (`expires_at = created_at + TTL + uniform(0, TTL × 0.2)`) so a burst of mints doesn't expire synchronously

Workers `LPOP` a session, do their work, then `RPUSH` it back on success or move it to a sick set on failure. A background maintainer keeps the pool topped up to target size.

```
ebay:pool:warm           LIST     SIDs ready for use
ebay:pool:sick           SET      SIDs awaiting GC
ebay:pool:session:{sid}  HASH     cookies_json, proxy_session, impersonate,
                                  created_at, expires_at, request_count, status
ebay:pool:mint_lock      STRING   global mint serialization
```

### Mint serialization across processes

`threading.Lock` is per-process. In a fleet of 4 gunicorn workers + a cron container, each worker has its own lock — they can all mint simultaneously when the pool drains, and overshoot the target by Nx.

Use a Redis-level lock with `SET ebay:pool:mint_lock 1 NX EX 30`. Acquire with a bounded wait (3s), release in a `finally:` block:

```python
def mint_one(*, respect_ceiling: bool = False) -> str | None:
    deadline = time.time() + 3.0
    while time.time() < deadline:
        if r.set(KEY_MINT_LOCK, '1', nx=True, ex=30):
            break
        time.sleep(0.1)
    else:
        return None  # contention timeout

    try:
        # Maintainer callers pass respect_ceiling=True so they no-op if
        # another worker has already filled the pool. Hitchhiker callers
        # (a real scrape waiting on a session) leave this False.
        if respect_ceiling and r.llen(KEY_WARM) >= TARGET_SIZE:
            return None
        meta = warmup_chain()                   # homepage GET → dwell → category GET
        store_session(meta)
        r.rpush(KEY_WARM, meta['sid'])
        return meta['sid']
    finally:
        r.delete(KEY_MINT_LOCK)
```

The maintainer's iteration becomes a `while LLEN(warm) < target: mint_one(respect_ceiling=True)` loop that re-reads the count between mints.

### TTL jitter: avoid the synchronous expiration stampede

When the pool's sessions are minted in a burst (after deploy, after a Redis flush, or at cold boot), a uniform TTL means they all expire within seconds of each other. The pool drains faster than serial mints can refill, and concurrent requests fall through to the no-pool path → captcha cascade.

Store a per-session jittered `expires_at` at mint time and verify staleness against it:

```python
expires_at = created_at + TTL + random.uniform(0, TTL * 0.2)

def is_stale(meta):
    if meta['request_count'] >= MAX_REQUESTS_PER_SESSION:
        return True
    return time.time() >= meta.get('expires_at', 0)
```

±20% jitter on a 7200s TTL spreads expirations across a ~24-minute window (0 to 0.2×7200s = 1440s of added jitter). The maintainer keeps pace.

### Pool-miss policy

When `checkout()` returns None (pool empty), there are two paths:

- **`fallback`** — skip the pool, run the scrape with `session=None`, fresh `impersonate="chrome"`, no warm cookies. Fast, but high block rate because the request has no `ak_bmsc`/`bm_sv` to ride on.
- **`inline_mint`** — block the caller for one mint cycle (~5–10s), then proceed with a freshly-warmed session. Slower but reliable.

Frontend / SLA-bound paths should default to `inline_mint`: a 5–10s slow page beats a captcha error. Background batch can use either; `inline_mint` is also recommended there since the worker has nothing better to do.

### Hitchhiker mints

The dedicated category-page warmup costs bandwidth. When a real request is already waiting (pool was empty when the caller hit checkout), skip the synthetic category GET — the real scrape will serve as the second warmup step:

```python
def execute_leg(scrape_call):
    meta = checkout()
    if meta is None:
        mint_one(skip_category=True)            # hitchhiker: homepage only
        meta = checkout()
    return scrape_call(meta)
```

Cuts ~50% of warmup bandwidth on the hitchhiker path. The session arrives with the homepage cookies; the real eBay request picks up the rest.

### Stream-aborted warmup

Akamai sets its cookies in the initial response headers. The full category-page body (often 1–2 MB) is wasted bandwidth on the warmup. Abort after ~64 KB:

```python
with session.stream('GET', category_url) as r:
    total = 0
    for chunk in r.iter_content(chunk_size=4096):
        total += len(chunk)
        if total >= 65_536:
            break
```

Real measurement on eBay's category search: full-page warmup ~1.5 MB; stream-aborted warmup ~150 KB per mint. Proxy providers bill the wire bytes — this directly cuts proxy spend.

### Cookie roll-forward

`bm_sv` rotates on most protected requests. On `return_session(success=True, cookies=live)`, persist the post-scrape cookie jar back into the session's hash so the next caller starts from the current server-side session state:

```python
def return_session(sid, success, cookies=None):
    if not success:
        mark_sick(sid)
        return
    if cookies:
        r.hset(session_key(sid), 'cookies_json', json.dumps(cookies))
    r.hincrby(session_key(sid), 'request_count', 1)
    r.rpush(KEY_WARM, sid)
```

Without roll-forward, sessions degrade as their stored cookies drift out of sync.

### Pre-warm at process boot

A cron or batch process running outside the maintainer-running fleet starts with an empty (or stale) local view of the pool. The first scrapes serially trigger hitchhiker mints — a cold-start tax of ~5–10s × N for the first N requests.

Front-load it: call `prewarm_pool()` once synchronously at process start. The mint lock serializes globally with the worker fleet's maintainer, so there's no double-mint risk.

```python
def main():
    args = parser.parse_args()
    prewarm_pool()                              # blocks ~30–60s cold, no-op when warm
    for item in items:
        scrape(item)
```

### Per-session telemetry

Persist these fields on every scrape's metrics row:

- `pool_sid` — which session served the request
- `pool_request_index` — how many requests this session has handled
- `pool_session_age_s` — wall-clock age at request time
- `pool_status_after` — `alive` / `sick` / `no_pool` (fallback was used)

Pool-wide gauges to graph: `LLEN warm` over time, `SCARD sick`, `TTL mint_lock` (>0 means a mint is in progress). Alert when `pool_status_after='no_pool'` rate exceeds 1% — the pool is draining faster than the maintainer can refill, indicating the target size is too low or the TTL jitter is too narrow for the current burst pattern.

## Block Detection

```python
import re

def detect_akamai_block(html):
    if 'Pardon Our Interruption' in html:
        return 'pardon'
    if 'Access Denied' in html and len(html) < 10_000:
        return 'access-denied'
    if 'Nous sommes' in html[:500]:
        return 'nous-sommes'                     # locale-specific Akamai deny
    if 'pageError' in html or 'page-error' in html:
        return 'rate_limit'                      # eBay app-level limiter
    if len(html) < 10_000 and re.search(r'Reference #\d+\.\w+', html):
        return 'akamai-ref'
    if len(html) < 30_000 and 'splashui' in html:
        return 'splashui'
    if len(html) < 5_000 and 'sensor_data' in html:
        return 'sensor-challenge'
    if len(html) < 5_000 and 'sec-cpt-if' in html:
        return 'crypto-challenge'
    return None
```

The `len(html)` guards prevent false positives — a real results page is 500KB+, block pages are typically <10KB. The `rate_limit` class (eBay's app-level limiter, distinct from an Akamai 403) drives an extra cooldown in the pool layer before the next checkout (`EBAY_POOL_RATE_LIMIT_BACKOFF_MIN_S` / `_MAX_S`, default 60–120s).

### Bot scoring cookie classes

Akamai's `_abck` cookie encodes the session's bot-score state. The cookie value ends in a suffix that signals the current state:

- `~0~-1~-1~-1` after a successful sensor_data post = **valid**, stop submitting sensors
- `~-1~-1~-1~-1` or `~0~-1~-1~-1` after a protected request = **invalidated**, the session has been downscored
- No `_abck` at all = the path is on Bot Manager Standard, no JS-validated session required

Tracking the `_abck` suffix class per response is the single most useful telemetry for understanding why a scraper is degrading.

## Operational Telemetry

For a scraper running at scale, log the following per request to make degradations visible:

- `session_id` and `session_age_seconds` — correlate burnt sticky IPs with their lifetime
- `proxy_provider` and `proxy_country` — partition success rates per pool
- `impersonate_target` — surface which fingerprint is currently winning vs losing
- `_abck_suffix_class` — `valid` / `invalidated` / `unset` per response (when the path serves it)
- `status` + response body length — needed to distinguish a real 200 from a 200-with-tarpit (Content Protector signature)
- `request_count_in_session` — high block rates on requests N+1 of an aging session = sticky lifetime is too long for the target's policy

Alert thresholds worth tuning:

- 24h success rate drops below 0.7× the 7-day average → Akamai rule rotation, run the impersonate probe
- 403-rate within the first 5 minutes of a session exceeds 20% → current fingerprint is burned, rotate target
- Per-ASN 403-rate exceeds 40% on a day when global average is <20% → that proxy provider's pool has degraded

## When Pure HTTP Hits Its Ceiling

Three signals indicate the pure-HTTP path can't be tuned further on a given target:

1. The target serves `_abck` and rejects requests without a server-validated sensor_data POST (visible as: every protected-path response returns the `_abck=...~0~-1~-1~-1~-1` invalidated form, regardless of fingerprint or IP).
2. The target ships Content Protector — symptoms include tarpitting (200 with slowed response body), deterministic 403 on a previously-mixed pattern, or first appearance of `sec-cpt` / `sbsd` cookies.
3. Sustained success rate sits below 30% across multiple proxy providers, multiple impersonate targets, and multiple pacing strategies — meaning the gate isn't any of the variables you control.

At that point the options are sensor_data forgery (Hyper Solutions paid API, or self-hosted port of the open-source `glizzykingdreko/akamai-v3-sensor-data-helper` encryption primitives plus a daily-updated payload generator) or migrating the cold-path requests to a stealth browser pool (Camoufox or Patchright). Both are significantly more expensive than the pure-HTTP path.
