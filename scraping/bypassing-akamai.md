# Bypassing Akamai Bot Manager with curl_cffi

How to scrape Akamai-protected pages using browser TLS impersonation and a pool of pre-warmed sessions — without a headless browser.

## What Akamai Detects

Akamai Bot Manager scores requests on a 0–100 scale starting with the very first request. The score combines signals from three gates: protocol-level fingerprint, IP/session reputation, and request pattern. Documentation often presents these as co-equal "all three must pass" requirements, but in practice **session trust dominates once you have a warm cookie jar** — a session that has built up a bot-manager cookie history through legitimate-looking navigation rides through subsequent requests largely independent of the IP's baseline reputation. The warm-pool architecture below is what makes a cheap residential proxy viable on Premier targets.

### Gate 1 — Protocol-level fingerprint

- **JA3/JA4 TLS fingerprinting** — cipher suite ordering, TLS extensions (including post-quantum X25519MLKEM768 on recent Chrome), and ALPN sequence. Akamai matches the handshake against a database of known-good browser profiles.
- **HTTP/2 fingerprint (Akamai format)** — concatenates `SETTINGS_LIST | WINDOW_UPDATE | PRIORITY_FRAMES | PSEUDO_HEADER_ORDER`. Each browser version has a stable string; any drift is a mismatch.
- **Header order + Sec-CH-UA consistency** — the UA major version must match the highest `Sec-CH-UA` brand version; `Sec-CH-UA-Mobile: ?1` must imply a mobile UA; Firefox/Safari UAs must NOT send Sec-CH-UA at all (those headers are Chromium-only).
- **Sec-Fetch-\* triad** — `Sec-Fetch-Site: none` for a typed URL, `same-origin`/`same-site`/`cross-site` for subsequent navigations.

### Gate 2 — IP / session reputation

Akamai operates Client Reputation, a global IP scoring system shared across all Akamai customers, but **session-level state accumulates trust on top of the IP baseline** and dominates the score for any request that already has a warm cookie jar.

- IP scoring still matters for the very first request from an unwarmed session: cheap residential pools carry shared abuse history that puts the first hit at a sub-zero baseline.
- Once the session carries bot-manager cookies and has done a few legitimate-looking page loads, subsequent requests are scored predominantly on the session, not the IP.
- This is why the warm pool turns a $1/GB residential proxy into 95%+ sustained success — you pay the IP-reputation cost once per session mint instead of once per request.
- Reputation decays over a ~30-day rolling window; IPs burned today stay flagged for weeks, but session warming pulls future requests out of that penalty range.

### The cookie names move

The classic Akamai jar is `ak_bmsc`, `bm_sz`, `bm_sv` and `_abck`. Tenants also run newer schemes — `bm_s`, `bm_ss`, `bm_so`, sometimes alongside `__uzm*` signals from a second bot vendor — and a tenant can switch schemes overnight. Never hard-code one name as "the" session cookie:

```python
BOT_MANAGER_COOKIES = ('ak_bmsc', 'bm_sz', 'bm_sv', '_abck', 'bm_s', 'bm_ss', 'bm_so')

if not any(name in session.cookies for name in BOT_MANAGER_COOKIES):
    raise BurnedSessionError('no_bot_manager_cookie')
```

A mint gate that only knows the old names rejects every healthy session the morning after a scheme change: the pool drains at TTL and cannot refill while the target is answering 200 to everything. Keep the old names for partial rollouts, add the new ones, and snapshot the whole jar by name rather than a fixed triple so the new cookies flow through untouched.

### Gate 3 — Request pattern (velocity + clustering)

Akamai aggregates request counts across multiple keys, **not per-IP alone**:

- ASN (autonomous system number) — all proxy provider exits share one ASN
- TLS fingerprint hash — even with rotating IPs, the same JA3 from the same ASN clusters
- URL template — 300 hits on the same search template in 5 minutes from one ASN trips the cluster threshold even if every individual IP is different.
- Time-of-day — 24/7 patterns or daily-heartbeat patterns at the same UTC minute get flagged.

Rotating IPs per request **does not defeat cluster detection** because the cluster key is multi-dimensional.

## Real-World Success Rate Bands

For a pure-HTTP scraper (curl_cffi + residential proxies, no JS execution):

| Path type | Expected sustained rate |
|---|---|
| Bot Manager Standard, no `_abck` validation | 85–95% with good config |
| Bot Manager Premier with `_abck` validation, no sensor forgery | 50–80% |
| Content Protector enabled (Akamai's 2024 scraper-specific product) | 30–60% |

Any documentation claiming "<5% block rate" is either outdated, run against unprotected paths, or measured before Akamai's recent rule updates. Large marketplaces running Premier + Content Protector are at the harder end of the range.

The dominant variable for sustained success rate is **session warmth**, not IP pool quality or fingerprint freshness. A perfect TLS impersonation with a fresh, unwarmed session through a clean residential pool still bottoms out at 30–60% on a Premier target. The same fingerprint through the cheapest $1/GB residential, but riding a warm jar from a homepage→category warmup, sustains 95%+ on marketplace-tier traffic. Proxy quality matters for the cold mint; the pool architecture matters for everything after.

## curl_cffi: Browser TLS Impersonation

[curl_cffi](https://github.com/lexiforest/curl_cffi) is a Python binding for libcurl that impersonates real browsers at the TLS level. Setting `impersonate="chrome"` (the alias tracks the newest target the installed version ships) reproduces that Chrome version's exact:

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
    proxy="http://user;sessid.X;sessttl.120:pass@gate.provider.com:port",  # sticky, see below
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

The warm-up requests and every scrape served by a session must share **the same impersonate target, the same sticky exit IP and the same curl options**. Splitting any of them (Chrome handshake for the warm-up, Firefox for the scrape; one IP for the homepage, another for the search) breaks the session coherence the whole model relies on.

### Picking the impersonate target

Pinning an explicit version (`impersonate="chrome131"`) means the scraper's wire image only changes when the library is upgraded — convenient for stability but easy to forget. The alias follows the library.

**The "best" impersonate target rotates over time.** Akamai's per-tenant ML auto-tunes its scoring; an impersonate that passed 100% last week may drop to 20% next week. Patterns observed in the field:

- For commerce sites whose real-user base is desktop Chrome on Windows/macOS, `chrome` consistently outperforms `firefox` / `chrome_android` / `safari_ios`. Akamai's prior probability is "this endpoint should be served from Chrome desktop", so a Chrome fingerprint matches the legitimate baseline.
- Mobile impersonations (`chrome_android`, `safari_ios`) work well on mobile-API endpoints but get flagged on desktop-oriented endpoints.
- `firefox` often works well on tenants where Firefox usage is significant in the user base, but worse on French/UK e-commerce sites where Firefox share is single-digit percent.

For sustained operation, run a small **probe** (20–30 requests across candidate impersonates against a cheap public path) whenever the success rate drifts, and pin the winner. Candidates worth probing:

```python
CANDIDATES = [
    "chrome",          # alias — latest stable Chrome
    "chrome131",       # one version back, sometimes survives longer
    "firefox",         # for tenants with significant Firefox user base
    "chrome_android",  # mobile path
    "safari_ios",      # mobile path
]
```

In an A/B against a large marketplace, a single pinned `chrome` target outperformed every rotation scheme tested. Pin the probe's winner; keep weighted sampling in the code for re-tuning, but do not rotate for the sake of rotating — a fleet of fingerprints from one ASN clusters just as well as one fingerprint.

### What NOT to set manually

curl_cffi's `impersonate=` already handles `User-Agent`, `Sec-CH-UA`, `Sec-CH-UA-Mobile`, `Sec-CH-UA-Platform`, `Accept`, and `Accept-Encoding` for the impersonated browser. Overriding these breaks the fingerprint:

- Wrong `Sec-CH-UA` version vs the UA's major version → strong bot signal.
- Adding `Sec-CH-UA-Wow64: ?0` with `Sec-CH-UA-Platform: "macOS"` → contradictory (Wow64 is Windows-only).
- Adding high-entropy hints (`Sec-CH-UA-Full-Version-List`, `Sec-CH-UA-Arch`, `Sec-CH-UA-Bitness`, `Sec-CH-UA-Platform-Version`) with mismatched values → worse than not sending them at all.

The general rule: if curl_cffi doesn't set a header for a given impersonate, do not invent values for it. Real Firefox doesn't send `Sec-CH-UA`; if you add it to a Firefox-impersonated request, you create the mismatch you were trying to avoid.

The only header consistently worth setting manually is `Accept-Language`, because curl_cffi doesn't localize this.

## IP Reputation: A Cost You Pay At Session Mint, Not Per Request

For a target with strong protocol-level scoring, IP pool quality determines how expensive each **session mint** is — i.e. how often the homepage→category warmup gets blocked before producing a usable jar. It does **not** determine the steady-state success rate of warm-session requests, which is dominated by session trust.

In practice, with a warm pool maintaining N pre-warmed sessions:

- The IP reputation cost is paid once per mint, then amortized across the requests that session serves before retirement.
- A cheap residential pool with a 50% mint success rate still ends up at 95%+ sustained throughput, because failed mints are retried at the maintainer layer and never reach the caller.
- Without a pool, every request pays the cold-mint penalty. There IP reputation matters directly and the cheapest tiers do bottom out at the rates below.

### Provider tiers — relevant for cold-mint cost, not sustained rate

- **Cheapest tier ($1–2/GB):** rough pool with significant shared abuse history. ~30–50% mint success on Akamai Premier; viable when a warm pool absorbs the misses.
- **Mid tier ($2–5/GB):** noticeably cleaner, 50–80% mint success. Less retry pressure on the maintainer.
- **Premium tier ($4–10/GB):** curated against pre-flagged IPs, 80–95% mint success, but mandatory KYC and minimum spends. Worth it if you don't have a pool, or if your scrape volume makes cold mints the bottleneck.

Benchmark a provider from the host that will run the scraper — gateways hand out different exit cohorts to different source networks — and keep the candidate out of the codebase until the numbers are in (see [Proxy Strategies](proxy-strategies.md)).

### Sticky-session lifetime

A session's exit IP must not change under its cookie jar. Ask the provider for a sticky window equal to the pool's session TTL: a 2-hour sticky session (`sessttl.120`) paired with a 2-hour pool TTL lets one warmed jar serve its request budget without the IP rotating mid-life. Verify that the gateway honours the requested value (some accept 120 minutes on ports whose documentation only mentions 30 — probe it: the control session rotates at the documented minute, the long one holds), and keep ±20% TTL jitter so long sessions do not expire synchronously.

The request budget per session is smaller than the sticky window suggests. An unvalidated session (no server-validated `_abck` sensor) gets sticky-blocked around **19–20 cumulative requests**; retire at **12** to leave margin for multi-request legs and concurrent-worker races. Age rarely retires a session before its count does; the TTL is the safety net.

Most rotating-residential providers offer sticky modes: session parameters in the username (`user-session-RANDOM-sessionduration-N`), per-port stickiness (a dedicated port range where each port is one sticky IP), or `sessid`/`sessttl` modifiers appended to the username (`user;sessid.X;sessttl.120`). Syntax differs; the model is the same.

### IP cleanup heuristic

When a sticky IP returns a 403, don't reuse it within the next hour. Akamai's per-IP score doesn't immediately recover, and burning more requests through a flagged IP only worsens the cluster signal for the same fingerprint+ASN combination.

## Request Pattern: The Velocity + Cluster Gate

The cluster-detection gate is the most counterintuitive of the three. Even with per-request IP rotation, 300 requests in 5 minutes from one proxy ASN, with the same TLS fingerprint, against the same URL template, trips Akamai's rate policy because the rate is keyed on `(ASN, fingerprint-hash, URL-template, time-window)`, not on the IP alone.

### Pacing

For a ~1,000-requests-per-day scraper:

- **Serial is better than parallel.** Two concurrent workers trigger per-IP burst rules even though throughput-wise you don't need parallelism at this volume.
- **Inter-request jitter of 10–60 seconds** on sequential batch paths. Uniform timing without jitter is detected as a botnet pattern.
- **Spread across the target's business day** (12–18 hours). 24/7 continuous activity is itself a signal.
- **Don't fire all daily traffic in one 5-minute burst.** Even at 1,000/day, a single nightly batch concentrates the cluster signal far more than the same volume spread over hours.

```python
import random
import time

time.sleep(random.uniform(10.0, 60.0))
```

### Retry pacing

When a request returns 403, immediately retrying against the same target with a new IP looks like a bot's retry loop. Sleep 30–120 s (random) before the retry, and after a site-level rate-limit page back off 60–120 s before the next pool checkout.

### Cookie discard on 403

If the session received bot-manager cookies before the 403, Akamai has flagged that session. Continued requests on the same session — even from a new IP — will fail. Retire the jar after any real block and start fresh; timeouts and proxy errors are not blocks and should not retire the jar.

## Pool Architecture: Sustained Multi-Worker Operation

The naive "fresh session per scrape" pattern pays the homepage→category warmup cost on every request and produces fingerprint+cookie trails that get flagged quickly. For sustained operation across a fleet — several web workers, cron jobs, batch backfills — a pre-warmed session pool is the right primitive.

### The model

Maintain a Redis-backed pool of N pre-warmed sessions (10–15 for a scraper serving both an interactive path and hourly sweeps). Each session carries:

- A sticky proxy session for its whole life (2 h, matching the pool TTL)
- A bot-manager cookie jar populated by a homepage → dwell → category warmup chain
- The impersonate target it was minted with (every later request reuses it)
- A per-session request counter — retire at 12 requests
- A **jittered** TTL (`expires_at = created_at + TTL + uniform(0, TTL × 0.2)`) so a burst of mints doesn't expire synchronously

Workers `LPOP` a session, do their work, then `RPUSH` it back on success or move it to a sick set on failure. A background maintainer keeps the pool topped up to target size.

```
pool:warm           LIST     session ids ready for use
pool:sick           SET      session ids awaiting GC
pool:session:{sid}  HASH     cookies_json, proxy_session, impersonate,
                             created_at, expires_at, request_count, status
pool:mint_lock      STRING   global mint serialization
```

### The warmup chain

```python
def mint(*, skip_category=False):
    sid = uuid.uuid4().hex[:12]
    proxy = sticky_proxy(sid, sessttl_min=120)
    impersonate = pick_impersonate()                 # pinned probe winner
    sess = make_session(impersonate, proxy)

    r = sess.get(HOMEPAGE)                           # step 1
    if r.status_code != 200:
        raise BurnedSessionError(f"homepage_{r.status_code}")
    if not any(c in sess.cookies for c in BOT_MANAGER_COOKIES):
        raise BurnedSessionError("no_bot_manager_cookie")

    if not skip_category:                            # step 2
        time.sleep(random.uniform(1.5, 3.5))         # human dwell
        sess.headers["Referer"] = HOMEPAGE
        with sess.stream("GET", CATEGORY_URL) as r:  # cookies arrive in the headers
            if r.status_code != 200:
                raise BurnedSessionError(f"category_{r.status_code}")
            read = 0
            for chunk in r.iter_content(4096):
                read += len(chunk)
                if read >= 65_536:                   # ~64 KB is enough
                    break

    return {"sid": sid, "proxy_session": proxy, "impersonate": impersonate,
            "cookies": dict(sess.cookies), "user_agent": sess.headers["User-Agent"],
            "created_at": time.time()}
```

Cap a mint at ~20 s. Any non-200 or missing cookie raises and the maintainer simply mints again on another sticky exit — the caller never sees the miss.

### Mint serialization across processes

`threading.Lock` is per-process. In a fleet of web workers plus a cron container, each process has its own lock — they can all mint simultaneously when the pool drains, and overshoot the target by N×.

Use a Redis-level lock with `SET pool:mint_lock 1 NX EX 30`. Acquire with a bounded wait (3 s), release in a `finally:` block:

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
        meta = mint()                                # homepage → dwell → category
        store_session(meta)
        r.rpush(KEY_WARM, meta['sid'])
        return meta['sid']
    finally:
        r.delete(KEY_MINT_LOCK)
```

The maintainer's iteration (every ~10 s) becomes a `while LLEN(warm) < target: mint_one(respect_ceiling=True)` loop that re-reads the count between mints.

### Checkout drains stale entries

A checkout that pops one stale entry and gives up returns nothing under load: stale sessions accumulate at the head of the list while fresh ones sit at the tail, and callers fall through to the no-pool path while usable sessions exist. Bound the scan by the list length at call time and return the first fresh entry:

```python
def checkout():
    for _ in range(r.llen(KEY_WARM)):
        sid = r.lpop(KEY_WARM)
        if not sid:
            return None                              # drained by a concurrent consumer
        meta = load_session(sid)
        if meta is None:
            continue
        if meta['request_count'] >= MAX_REQUESTS or time.time() >= meta['expires_at']:
            mark_sick(sid, 'stale_on_checkout')
            continue
        return meta
    return None
```

### TTL jitter: avoid the synchronous expiration stampede

When the pool's sessions are minted in a burst (after a deploy, after a Redis flush, or at cold boot), a uniform TTL means they all expire within seconds of each other. The pool drains faster than serial mints can refill, and concurrent requests fall through to the no-pool path → captcha cascade.

Store a per-session jittered `expires_at` at mint time and verify staleness against it: ±20% jitter on a 7200 s TTL spreads expirations across a ~24-minute window. The maintainer keeps pace.

### Pool-miss policy

When `checkout()` returns None (pool empty), there are two paths:

- **`fallback`** — skip the pool, run the scrape with a fresh un-warmed session. Fast, but a high block rate because the request has no jar to ride on.
- **`inline_mint`** — block the caller for one mint cycle (~5–10 s), then proceed with a freshly-warmed session. Slower but reliable.

Interactive / SLA-bound paths should default to `inline_mint`: a 5–10 s slow page beats a captcha error. Batch paths always inline-mint; the worker has nothing better to do.

### Hitchhiker mints

The dedicated category-page warmup costs bandwidth. When a real request is already waiting (pool was empty when the caller hit checkout), skip the synthetic category GET — the real scrape serves as the second warmup step:

```python
def execute_leg(scrape_call):
    meta = checkout()
    if meta is None:
        mint_one(skip_category=True)            # hitchhiker: homepage only
        meta = checkout()
    return scrape_call(meta)
```

Cuts ~50% of warmup bandwidth on the hitchhiker path, and the session's URL sequence looks less synthetic. The maintainer's pre-fill keeps the full two-step chain.

### Stream-aborted warmup

Akamai sets its cookies in the initial response headers. The full category-page body (often 1–2 MB) is wasted bandwidth on the warmup. Streaming the response and aborting after ~64 KB brings a mint from ~1.5 MB to ~150 KB on the wire. Proxy providers bill wire bytes — this directly cuts proxy spend. Akamai's documented HTTP/2 scoring is on request-side initialisation; no detection of response-side early close has been observed.

### Cookie roll-forward

The session cookie rotates on most protected requests. On `return_session(success=True, cookies=live)`, persist the post-scrape cookie jar back into the session's hash so the next caller starts from the current server-side session state:

```python
def return_session(sid, success, cookies=None):
    if not success:
        mark_sick(sid)
        return
    if cookies:
        r.hset(session_key(sid), 'cookies_json', json.dumps(cookies))
    if r.hincrby(session_key(sid), 'request_count', 1) >= MAX_REQUESTS:
        mark_sick(sid, 'exhausted')
        return
    r.rpush(KEY_WARM, sid)
```

Without roll-forward, sessions degrade as their stored cookies drift out of sync.

### Retry budget per leg

A scrape "leg" (one logical fetch, possibly several pages) runs through the pool with a small retry budget, and only one failure class earns a retry:

- **Block page** (captcha / bot-manager deny): mark the session sick, back off, retry on another session.
- **Site-level rate-limit page** (the target's own limiter, distinct from the bot manager): mark sick and sleep 60–120 s before the next checkout.
- **Timeout, stall, or proxy error**: mark the session sick and stop — retrying a hung exit burns the deadline.
- **Success**: return the session with rolled-forward cookies.

Classify a "success" with a tiny body (under ~5 KB for a page that is normally hundreds of KB) as a tarpit, not a success, and a response that took more than ~12 s as a stall.

### Pre-warm at process boot

A cron or batch process running outside the maintainer-running fleet starts with an empty (or stale) local view of the pool. The first scrapes serially trigger hitchhiker mints — a cold-start tax of ~5–10 s × N for the first N requests.

Front-load it: call `prewarm_pool()` once synchronously at process start. The mint lock serializes globally with the worker fleet's maintainer, so there's no double-mint risk.

### When the endpoint requires a login

Targets sometimes move an endpoint behind a sign-in wall. A logged-in cookie jar passes it without the pool, but a single account must stay gentle: run that jar from **one stable IP** (no proxy rotation — the account's login is bound to it), pace it with a fixed delay of about 2 s between pages, and keep the warm pool for every path that does not need the identity.

### Per-session telemetry

Persist these fields on every scrape's metrics row:

- `pool_sid` — which session served the request
- `pool_request_index` — how many requests this session has handled
- `pool_session_age_s` — wall-clock age at request time
- `pool_status_after` — `alive` / `sick` / `no_pool` (fallback was used)

Pool-wide gauges to graph: `LLEN warm` over time, `SCARD sick`, `TTL mint_lock` (>0 means a mint is in progress). Alert when the `no_pool` rate exceeds 1% — the pool is draining faster than the maintainer can refill, indicating the target size is too low or the TTL jitter is too narrow for the current burst pattern.

## Block Detection

```python
import re

def detect_block(html):
    if 'Pardon Our Interruption' in html:
        return 'pardon'
    if 'Access Denied' in html and len(html) < 10_000:
        return 'access-denied'
    if 'Nous sommes' in html[:500]:
        return 'nous-sommes'                     # locale-specific deny page
    if 'pageError' in html or 'page-error' in html:
        return 'rate_limit'                      # the site's own limiter, not the bot manager
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

The `len(html)` guards prevent false positives — a real results page is 500 KB+, block pages are typically <10 KB. Treat the site's own rate-limit page as its own class: it drives the 60–120 s cooldown in the pool layer, whereas a bot-manager deny retires the session.

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
- `request_count_in_session` — high block rates on requests N+1 of an aging session = the request budget is too high for the target's policy

Alert thresholds worth tuning:

- 24 h success rate drops below 0.7× the 7-day average → Akamai rule rotation, run the impersonate probe
- 403 rate within the first 5 minutes of a session exceeds 20% → current fingerprint is burned, rotate target
- Mint failure rate jumps while the target answers 200 to a browser → check the cookie-name gate first, then the proxy

## When Pure HTTP Hits Its Ceiling

Three signals indicate the pure-HTTP path can't be tuned further on a given target:

1. The target serves `_abck` and rejects requests without a server-validated sensor_data POST (visible as: every protected-path response returns the `_abck=...~0~-1~-1~-1~-1` invalidated form, regardless of fingerprint or IP).
2. The target ships Content Protector — symptoms include tarpitting (200 with slowed response body), deterministic 403 on a previously-mixed pattern, or first appearance of `sec-cpt` / `sbsd` cookies.
3. Sustained success rate sits below 30% across multiple proxy providers, multiple impersonate targets, and multiple pacing strategies — meaning the gate isn't any of the variables you control.

At that point the options are sensor_data forgery (paid APIs, or a self-hosted port of the open-source `akamai-v3-sensor-data-helper` encryption primitives plus a daily-updated payload generator) or migrating the cold-path requests to a stealth browser pool (Camoufox or Patchright). Both are significantly more expensive than the pure-HTTP path.
