# Bypassing AWS WAF with Proof-of-Work Token Generation

How to solve AWS WAF challenges programmatically using curl_cffi, a proof-of-work solver, and browser fingerprint emulation -- without a headless browser.

## What AWS WAF Does

AWS WAF's bot control is fundamentally different from Akamai and Cloudflare:

- **Proof-of-Work challenges** -- the server sends a JS challenge requiring a nonce via SHA-256 hashcash or scrypt
- **Bandwidth challenges** -- requires uploading a blob of null bytes (1KB to 10MB) via multipart POST
- **Browser fingerprinting** -- the challenge SDK (`challenge.js`) collects WebGL renderer, canvas hash, plugin list, crypto API capabilities, and automation detection signals
- **Token binding** -- solved tokens are bound to the TLS session (same curl_cffi session must be reused)
- **CAPTCHA layering** -- image CAPTCHAs can appear at any point

Unlike Akamai (TLS fingerprint + behavioral) or Cloudflare (cookie-based JS challenges), AWS WAF requires **active computation** -- you must solve proof-of-work puzzles and submit browser-like fingerprint payloads.

## Challenge Detection

AWS WAF challenges are detected by two markers in the HTML:

```python
def is_waf_challenge(resp):
    if 'gokuProps' in resp.text:
        return True
    if 'challenge.js' in resp.text and 'awswaf' in resp.text:
        return True
    return False
```

`gokuProps` is a JSON object embedded in the challenge page containing the challenge parameters (AWS WAF's internal codename).

## Solving the Challenge

The solver reproduces what `challenge.js` does in a real browser:

```
1. Extract gokuProps + challenge.js endpoint from HTML
2. GET /inputs?client=browser -> receive challenge type + difficulty
3. Build browser fingerprint payload
4. Solve PoW (hashcash or scrypt) or generate bandwidth blob
5. POST /verify or /mp_verify with solution + fingerprint
6. Receive aws-waf-token
7. Inject token as cookie + request header for subsequent requests
```

### Step 1: Extract Challenge Parameters

```python
def extract_waf_params(html):
    goku_props = json.loads(
        html.split("window.gokuProps = ")[1].split(";")[0]
    )
    host = html.split('src="https://')[1].split("/challenge.js")[0]
    return goku_props, host
```

### Step 2: Get Challenge Inputs

```python
def get_inputs(session, endpoint):
    return session.get(
        f"https://{endpoint}/inputs?client=browser",
        headers=waf_headers,
    ).json()
```

Three challenge types exist:

| Type | Method | Endpoint |
|------|--------|----------|
| SHA-256 hashcash | Find nonce where `SHA256(input+checksum+nonce)` has N leading zero bits | `/verify` |
| scrypt PoW | Find nonce where `scrypt(input+checksum+nonce)` has N leading zero bits | `/verify` |
| NetworkBandwidth | Upload base64 null bytes (1KB-10MB based on difficulty) | `/mp_verify` |

### Step 3: Browser Fingerprint

The fingerprint payload must look like a real Chrome browser's `challenge.js` output:

```python
def build_fingerprint(user_agent):
    gpu = random.choice(gpu_database)  # JSON file with real WebGL profiles

    fp = {
        "plugins": [
            {"name": "PDF Viewer"},
            {"name": "Chrome PDF Viewer"},
            {"name": "Chromium PDF Viewer"},
            {"name": "Microsoft Edge PDF Viewer"},
            {"name": "WebKit built-in PDF"},
        ],
        "screenInfo": "1920-1080-1032-24-*-*-*",
        "userAgent": user_agent,
        "webDriver": False,
        "gpu": {
            "vendor": gpu["webgl_unmasked_vendor"],
            "model": gpu["webgl_unmasked_renderer"],
            "extensions": gpu["webgl_extensions"].split(";"),
        },
        "canvas": {
            "hash": random.randrange(645172295, 735192295),
            "histogramBins": [random.randrange(0, 40) for _ in range(256)],
        },
        "crypto": {
            "subtle": 1, "encrypt": True, "decrypt": True,
            "sign": True, "verify": True, "digest": True,
            "deriveBits": True, "deriveKey": True,
            "getRandomValues": True, "randomUUID": True,
        },
        "automation": {
            "wd": {"properties": {"document": [], "window": [], "navigator": []}},
            "phantom": {"properties": {"window": []}},
        },
        "version": "2.4.0",  # WAF SDK version
        "id": str(uuid.uuid4()),
    }

    checksum, encrypted_data = encode_with_crc(fp)
    return checksum, encrypted_data
```

Key elements:

- **GPU data**: randomized from a database of real WebGL renderers (NVIDIA, AMD, Intel)
- **Canvas hash**: randomized within a realistic range
- **Automation detection**: reports "no automation detected" (`webDriver: false`, empty property arrays)
- **CRC checksum**: payload is CRC32-checksummed and encrypted before transmission

### Step 4: Solve Proof-of-Work

**SHA-256 hashcash** (brute-force up to 50M iterations):

```python
def hash_pow(challenge_input, checksum, difficulty):
    combined = (challenge_input + checksum).encode()
    for nonce in range(50_000_000):
        digest = hashlib.sha256(combined + str(nonce).encode()).digest()
        full_bytes, remainder = divmod(difficulty, 8)
        if digest[:full_bytes] != b"\x00" * full_bytes:
            continue
        if remainder and (digest[full_bytes] >> (8 - remainder)):
            continue
        return str(nonce)
```

**scrypt** (using `hashlib.scrypt` via OpenSSL -- 366x faster than pure-Python pyscrypt):

```python
def compute_scrypt_nonce(challenge_input, checksum, difficulty):
    combined = challenge_input + checksum
    for nonce in range(10_000_000):
        result = hashlib.scrypt(
            f"{combined}{nonce}".encode(),
            salt=checksum.encode(),
            n=128, r=8, p=1, dklen=16,
        )
        if leading_zero_bits(result) >= difficulty:
            return str(nonce)
```

**Bandwidth challenge** (no computation -- just upload):

```python
def compute_bandwidth(challenge_input, checksum, difficulty):
    size_map = {1: 1024, 2: 10240, 3: 102400, 4: 1048576, 5: 10485760}
    return base64.b64encode(b"\x00" * size_map.get(difficulty, 1024)).decode()
```

### Step 5: Submit the Solution

**Standard challenges** (`/verify`, JSON):

```python
def verify(session, endpoint, payload):
    return session.post(
        f"https://{endpoint}/verify",
        json=payload,
        headers=waf_headers,
    ).json().get("token", "")
```

**Bandwidth challenges** (`/mp_verify`, multipart):

```python
def mp_verify(session, endpoint, solution_data, metadata):
    from curl_cffi import CurlMime
    mime = CurlMime()
    mime.addpart(name="solution_data", filename="blob",
                 data=solution_data.encode(),
                 content_type="application/octet-stream")
    mime.addpart(name="solution_metadata", filename="blob",
                 data=json.dumps(metadata).encode(),
                 content_type="application/json")
    return session.post(
        f"https://{endpoint}/mp_verify",
        multipart=mime,
    ).json().get("token", "")
```

### Step 6: Inject the Token

Set the token as both a cookie and a request header:

```python
def inject_waf_token(session, token, domain):
    bare_domain = f".{domain.removeprefix('www.')}"
    try:
        session.cookies.jar.clear(bare_domain, "/", "aws-waf-token")
    except KeyError:
        pass
    session.cookies.set("aws-waf-token", token, domain=bare_domain, path="/")
    # Also pass as header on the retry request
    return {"x-aws-waf-token": token}
```

## Retry Strategy

The solver should retry up to 3 times with backoff:

```python
def solve_waf(session, html, domain):
    goku_props, endpoint = extract_waf_params(html)
    waf_session = session  # reuse same TLS session (token is bound to it)

    for attempt in range(3):
        inputs = get_inputs(waf_session, endpoint)

        if inputs.get("challenge_type") == BANDWIDTH_TYPE:
            solution, metadata = build_bandwidth_payload(inputs)
            token = mp_verify(waf_session, endpoint, solution, metadata)
        else:
            payload = build_standard_payload(inputs)
            token = verify(waf_session, endpoint, payload)

        if token:
            return token
        time.sleep(1 + attempt)

    return None
```

### Proxy DNS Fallback

Some proxy DNS resolvers can't resolve dynamically-generated WAF token subdomains (`*.token.awswaf.com`). If the proxied solve fails, retry without proxy -- WAF tokens are **not IP-bound**:

```python
if has_proxy and not token:
    direct_session = CurlSession(impersonate="chrome145")  # no proxy
    token = solve_waf(direct_session, html, domain)
```

## CAPTCHA Handling

Image CAPTCHAs can appear alongside WAF challenges. Use a CAPTCHA solving service:

```python
def solve_captcha(session, captcha_page_url, html):
    img = BeautifulSoup(html, 'lxml').select_one('img[src*="captcha"]')
    if not img:
        return False  # might be an interstitial, not a real CAPTCHA

    img_b64 = base64.b64encode(session.get(img['src']).content).decode()

    # CapSolver ImageToTextTask -- synchronous, result in response
    resp = requests.post('https://api.capsolver.com/createTask', json={
        'clientKey': api_key,
        'task': {'type': 'ImageToTextTask', 'body': img_b64},
    }).json()

    solution = resp['solution']['text']
    session.get(action_url, params={**hidden_fields, 'field-keywords': solution})
```

Not all "CAPTCHA pages" are real CAPTCHAs -- sometimes the target serves a form with hidden fields that just needs to be submitted (interstitial acknowledgment).

## Results

- Solve time: ~1-2s per WAF challenge (PoW computation)
- No headless browser needed
- Token can be reused for hours (session-bound)
- CapSolver cost: ~$0.001 per image CAPTCHA (rare)
