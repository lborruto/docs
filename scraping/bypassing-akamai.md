# Bypassing Akamai Bot Manager with curl_cffi

How to scrape Akamai-protected pages using Chrome TLS impersonation -- without a headless browser.

## What Akamai Detects

Akamai Bot Manager performs:

- **JA3/JA4 TLS fingerprinting** -- each TLS library (Python requests, Go net/http, Node axios) produces a unique fingerprint from cipher suite ordering, TLS extensions, and ALPN. Akamai maintains a database of known bot fingerprints and blocks non-browser signatures outright.
- **HTTP/2 fingerprinting** -- compares the HTTP/2 SETTINGS frame, WINDOW_UPDATE cadence, header order (`:method`, `:path`, `:authority`, `:scheme`), and HPACK encoding against known browser profiles.
- **Behavioral analysis** -- cross-IP correlation on request patterns. Back-to-back requests at machine speed get flagged even with rotating IPs.
- **JavaScript challenges** -- "Pardon Our Interruption" interstitial pages with sensor_data/crypto challenges requiring JS execution.

Standard Python HTTP clients (`requests`, `httpx`, `aiohttp`) get blocked immediately. Even with perfect headers, the TLS handshake alone identifies them as bots.

## curl_cffi: Chrome TLS Impersonation

[curl_cffi](https://github.com/lexiforest/curl_cffi) is a Python binding for libcurl that can impersonate real browsers at the TLS level. Setting `impersonate="chrome"` reproduces Chrome's exact:

- TLS cipher suite ordering and extensions (including post-quantum X25519MLKEM768)
- HTTP/2 SETTINGS frame values (`HEADER_TABLE_SIZE=65536`, `INITIAL_WINDOW_SIZE=6291456`, etc.)
- HTTP/2 priority headers (`u=0, i`)
- ALPN negotiation sequence
- All Sec-CH-UA, User-Agent, and Accept headers matching the impersonated Chrome version

```python
from curl_cffi.requests import Session as CurlSession
from curl_cffi.const import CurlOpt

session = CurlSession(
    impersonate="chrome",
    timeout=10,
    allow_redirects=True,
    headers={"Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"},
    proxy="http://user:pass@gate.provider.com:port",
    curl_options={
        CurlOpt.TCP_KEEPALIVE: 1,
        CurlOpt.TCP_KEEPIDLE: 60,
        CurlOpt.TCP_KEEPINTVL: 30,
        CurlOpt.DNS_CACHE_TIMEOUT: 300,
        CurlOpt.MAXCONNECTS: 10,
        CurlOpt.PIPEWAIT: 1,           # HTTP/2 multiplexing
        CurlOpt.CONNECTTIMEOUT_MS: 3000,
        CurlOpt.IPRESOLVE: 1,          # IPv4-only -- skip AAAA + Happy Eyeballs
    },
)

resp = session.get("https://target.example.com/search?q=test")
```

### What NOT to Set Manually

curl_cffi's `impersonate=` handles User-Agent, Sec-CH-UA, Sec-CH-UA-Mobile, Sec-CH-UA-Platform, Accept, and Accept-Encoding automatically. **Do not override these** -- conflicting headers (e.g. wrong Sec-CH-UA version) cause Akamai to detect a mismatch between the TLS fingerprint and the declared browser identity.

The only header worth setting manually is `Accept-Language`, because curl_cffi doesn't localize this. Randomize it for entropy:

```python
_ACCEPT_LANGUAGES = [
    "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "fr-FR,fr;q=0.9,en-US;q=0.5,en;q=0.3",
    "fr-FR,fr;q=0.9",
]

headers = {"Accept-Language": random.choice(_ACCEPT_LANGUAGES)}
```

### TLS Fingerprint Verification

Verified against `tls.peet.ws`:

- TLS extension 17613 (ALPS): present
- HTTP/2 Akamai fingerprint: `1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p`
- All 17 HTTP/2 headers in correct Chrome order
- Post-quantum X25519MLKEM768: supported

4 runtime divergences remain unfixable (WINDOW_UPDATE cadence, stream dependencies, HPACK encoding, TLS ALPS behavior) but these are weak signals, not blocking triggers.

## Block Detection

Akamai uses several block response patterns. Detect them by content + size:

```python
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

The `len(html)` guards prevent false positives -- a real results page is 500KB+, block pages are typically <10KB.

## Avoiding Behavioral Detection

TLS impersonation alone isn't enough. Akamai performs cross-IP behavioral correlation, so machine-speed request patterns get flagged even with rotating proxies. Add jittered delays between requests:

```python
delay = random.uniform(1.0, 3.0)
time.sleep(delay)
```

If you start getting blocked, back off. A simple escalation pattern: track how many blocks you've hit recently, and if it crosses a threshold (e.g. 3 blocks in 2 minutes), double your delays for a cooldown period.

## Results

- Typical latency: 1-2s per request
- Block rate: <1% with proper delays
- No headless browser needed
- No JavaScript execution needed
