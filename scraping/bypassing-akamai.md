# Bypassing Akamai Bot Manager with curl_cffi

How to scrape Akamai-protected pages using Chrome TLS impersonation — without a headless browser.

## What Akamai Detects

Akamai Bot Manager scores requests on a 0–100 scale starting with the very first request. The score combines signals from three independent gates: protocol-level fingerprint, IP reputation, and request pattern. **All three matter; passing only two is not enough.** Most documentation focuses on the fingerprint gate alone, which is why "use curl_cffi" advice often fails in production.

### Gate 1 — Protocol-level fingerprint

- **JA3/JA4 TLS fingerprinting** — cipher suite ordering, TLS extensions (including post-quantum X25519MLKEM768 on recent Chrome), and ALPN sequence. Akamai matches the handshake against a database of known-good browser profiles.
- **HTTP/2 fingerprint (Akamai format)** — concatenates `SETTINGS_LIST | WINDOW_UPDATE | PRIORITY_FRAMES | PSEUDO_HEADER_ORDER`. Each browser version has a stable string; any drift is a mismatch.
- **Header order + Sec-CH-UA consistency** — the UA major version must match the highest `Sec-CH-UA` brand version; `Sec-CH-UA-Mobile: ?1` must imply mobile UA; Firefox/Safari UAs must NOT send Sec-CH-UA at all (those headers are Chromium-only).
- **Sec-Fetch-\* triad** — `Sec-Fetch-Site: none` for a typed URL, `same-origin`/`same-site`/`cross-site` for subsequent navigations.

### Gate 2 — IP reputation

Akamai operates Client Reputation, a global scoring system shared across all Akamai customers. An IP that scraped bank A carries a negative score when it hits retailer B. Two key consequences:

- Cheap residential proxy pools (anything in the $1/GB range) carry significant shared abuse history from other scraping customers. Even your first request from a "fresh" sticky IP arrives with a sub-zero baseline.
- Reputation decays over a ~30-day rolling window. IPs burned today stay flagged for weeks.

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

The dominant variable for a target's success rate is **IP pool quality**, not fingerprint freshness. A perfect TLS impersonation through a burned residential pool will sit at 10–25%. The same fingerprint through a clean pool will hit 70–90%. Proxy choice is roughly half the battle.

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

The `chrome` alias auto-tracks the latest target curl_cffi ships. As of `curl_cffi==0.15.1b1` that resolves to `chrome146`. Pinning the explicit version (`impersonate="chrome146"`) means your scraper's wire image only changes when you upgrade the library — convenient for stability but easy to forget.

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

### What NOT to set manually

curl_cffi's `impersonate=` already handles `User-Agent`, `Sec-CH-UA`, `Sec-CH-UA-Mobile`, `Sec-CH-UA-Platform`, `Accept`, and `Accept-Encoding` for the impersonated browser. Overriding these breaks the fingerprint:

- Wrong `Sec-CH-UA` version vs the UA's major version → strong bot signal.
- Adding `Sec-CH-UA-Wow64: ?0` with `Sec-CH-UA-Platform: "macOS"` → contradictory (Wow64 is Windows-only).
- Adding high-entropy hints (`Sec-CH-UA-Full-Version-List`, `Sec-CH-UA-Arch`, `Sec-CH-UA-Bitness`, `Sec-CH-UA-Platform-Version`) with mismatched values → worse than not sending them at all.

The general rule: if curl_cffi doesn't set a header for a given impersonate, do not invent values for it. Real Firefox doesn't send `Sec-CH-UA`; if you add it to a Firefox-impersonated request, you create the mismatch you were trying to avoid.

The only header consistently worth setting manually is `Accept-Language`, because curl_cffi doesn't localize this.

## IP Reputation: The Dominant Variable

For a target with strong protocol-level scoring, IP pool quality determines roughly half the sustained success rate. The cheap-residential market is a known stressor for Akamai-protected sites.

### Provider tiers (general observations from public benchmarks and field testing)

- **Cheapest tier ($1–2/GB):** rough pool with significant shared abuse history. Effective ceiling around 30–50% on Akamai Premier targets even with perfect fingerprint.
- **Mid tier ($2–5/GB):** noticeably cleaner. Decodo, IPRoyal standard, SOAX premium reach 50–80% on most Akamai-protected paths.
- **Premium tier ($4–10/GB):** Bright Data, Oxylabs, NodeMaven specifically curate against pre-flagged IPs. Sustained 80–95% on most targets, but mandatory KYC and minimum spends.

### Sticky-session lifetime

When the target serves an `ak_bmsc` or `bm_sv` cookie, reusing the same IP for multiple requests lets that cookie's session state accumulate trust. 10–30 minutes per sticky IP is the typical sweet spot — long enough to amortize cookie warming, short enough to limit damage if Akamai escalates scoring mid-session.

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

## Block Detection

```python
import re

def detect_akamai_block(html):
    if 'Pardon Our Interruption' in html:
        return 'pardon'
    if 'Access Denied' in html and len(html) < 10_000:
        return 'access-denied'
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

The `len(html)` guards prevent false positives — a real results page is 500KB+, block pages are typically <10KB.

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
