# Proxy Strategies for Web Scraping

Choosing the right proxy type depends on your use case, not on which anti-bot system you're bypassing. This article covers the two main proxy models and when to use each.

## Rotating Residential vs ISP Sticky

| | Rotating Residential | ISP Sticky |
|--|---------------------|------------|
| **IP per request** | New IP every request | Same IP across requests |
| **Session persistence** | None -- stateless | Cookies persist across requests |
| **ASN diversity** | High (thousands of ASNs) | Low (often single ASN) |
| **IP classification** | Residential (real ISP subscribers) | Varies -- often flagged as hosting/proxy |
| **Cost model** | Per GB (~$1-3/GB) | Per IP per month (~$3-6/IP) |
| **Best for** | Stateless scraping at scale | Login flows, authenticated sessions |

### Rotating Residential

Use when each request is independent and you don't need cookies to persist:

```python
from curl_cffi.requests import Session as CurlSession

session = CurlSession(
    impersonate="chrome",
    proxy="http://user:pass@gate.provider.com:port",
)
# Provider rotates exit IP on every request
resp = session.get("https://target.example.com/search?q=test")
```

No per-IP health tracking, no cookie warming, no session management. Each request is a fresh IP.

### ISP Sticky

Use when cookies obtained during one request must be sent from the same IP later (e.g. after login):

```python
import uuid

def get_sticky_proxy(base_user, password, host, port, sessttl_min=120):
    """Random session ID -> same IP for the next sessttl_min minutes.

    Username/password syntax varies by provider. The example below uses
    DataImpulse's `;sessid.X;sessttl.N` modifier appended to the username
    (semicolon-delimited, N in minutes).
    """
    sid = uuid.uuid4().hex[:12]
    username = f"{base_user};sessid.{sid};sessttl.{sessttl_min}"
    return f"http://{username}:{password}@{host}:{port}"

proxy = get_sticky_proxy("user__cr.fr", "pw", "gw.dataimpulse.com", 823)
session = CurlSession(impersonate="chrome", proxy=proxy)
```

The `sessttl` value pins the exit IP for that many minutes. Use a deterministic `sessid` (e.g. `sha256(account_id)[:12]`) when you need the same IP for a specific account across processes; a random `sessid` is fine when you just need within-process stickiness.

## The French ISP Proxy Problem

If you need French IPs, be aware of a structural limitation:

- **All French ISP proxies are Orange** -- every provider delivers IPs on AS5511/AS3215. Free (AS12322), SFR (AS15557), Bouygues (AS5410) don't participate in IP-leasing markets.
- **0% residential classification** on IP2Location -- the IPs are technically ISP IPs but classified as hosting/proxy.
- **Single-ASN correlation** -- anti-bot systems detect that all your IPs share the same ASN. We hit a ceiling of ~100-150 requests before blocks cascaded.
- **Confirmed by providers** -- a French proxy provider told us: "en FR, c'est impossible d'avoir des IPs categorisees ISP" on IP2Location.

Rotating residential proxies avoid this entirely: each request is a different IP from a different ASN.

### Does IP Classification Matter?

| Anti-Bot System | IP Intelligence Source | Uses IP2Location? |
|----------------|----------------------|-------------------|
| **Akamai Bot Manager** | Own proprietary (~30% global traffic) | No |
| **Cloudflare Enterprise** | Own internal (~20% global traffic) | No |
| **DataDome** | Own ML + likely IP2Location (~25-30% of score) | Probably |

Akamai and Cloudflare have enough traffic to build their own IP databases. Third-party classification is irrelevant for them -- but the single-ASN problem still applies.

## Rate Limiting

### With Rotating Proxies

No per-IP state to manage. Focus on **behavioral** delays -- prevent detectable patterns across the IP pool:

```python
import random
import time

delay = random.uniform(1.0, 3.0)  # jittered delay
time.sleep(delay)
```

If blocks start appearing, escalate: double your delays for a cooldown period. A good threshold is 3 blocks within 2 minutes triggering a 120-second backoff.

### With Sticky Proxies

Rate limit per account/session, not per IP:

```python
class RateLimiter:
    def __init__(self, min_delay=0.5, max_delay=1.5):
        self._last_request = {}

    def wait(self, key):
        jitter = random.uniform(0, self._max_delay - self._min_delay)
        earliest = self._last_request.get(key, 0) + self._min_delay + jitter
        sleep_for = max(0, earliest - time.time())
        if sleep_for > 0:
            time.sleep(sleep_for)
        self._last_request[key] = time.time()
```

## Scraper API Alternative

All proxy management (rotation, rate limiting, TLS impersonation, challenge solving) can be offloaded to a scraper API:

```python
import requests

# One HTTP call replaces all proxy/session/impersonation code
response = requests.get("http://api.scrape.do/", params={
    "url": "https://target.example.com/page",
    "token": SCRAPEDO_TOKEN,
    "geoCode": "FR",
}, timeout=30)
```

Trade-offs:

| | Self-managed | Scraper API |
|--|-------------|-------------|
| **Cost** | ~$6-30/mo (proxies) | ~$29-99/mo |
| **Infrastructure** | Proxy config, rate limiting, cookies, challenge solvers | One env var |
| **Control** | Full | None (black box) |
| **Reliability** | 95%+ (depends on tuning) | ~100% (provider handles bypass) |
| **Vendor lock-in** | None | Single point of failure |
