# jackstream in Docker

Self-hosted Stremio addon that queries Jackett and streams torrents via an embedded WebTorrent client. No debrid, no qBittorrent, no shared volume. One container, zero persistent storage.

Source: <https://github.com/lborruto/jackstream>

## Why build this

Stremio + Jackett + WebTorrent is the right stack for a homelab that wants torrent streaming **inside Stremio**, on any device on the LAN, without:

- Debrid accounts (monthly fee, third-party dependency)
- qBittorrent running alongside (needs a shared volume for the `.torrent` download path, and its own credential juggling for private trackers)
- Rewriting each private tracker's auth into every addon

jackstream takes the IMDB id Stremio sends, asks the local Jackett for torrents, and streams them via WebTorrent. Because Jackett proxies the `.torrent` URL (with passkeys for private trackers embedded in the announce URLs), WebTorrent connects to private trackers out of the box — no cookies to manage.

## How it works

```
Stremio app
    │ GET /{config}/manifest.json
    │ GET /{config}/stream/{type}/{id}.json
    ▼
[Express + Stremio addon]
    │
    ├─ Resolve IMDB id → titles via TMDB (24 h cache)
    ├─ Search Jackett in parallel across title variants
    ├─ Parse + sort torrents (quality > source > hdr > seeders)
    └─ Return streams pointing back to /stream/{config}/{torrentId}/{fileIdx}

    │ GET /stream/:config/:torrentId/:fileIdx
    ▼
[WebTorrent singleton]
    │
    ├─ Download .torrent via Jackett (with passkeys)
    ├─ Sequential priority, critical first pieces
    ├─ Wait for STREAM_READY_MB then serve with Range support
    └─ Clean up idle torrents, respect maxConcurrentTorrents
```

### Key architectural choices

- **Zero server-side storage.** Credentials (Jackett + TMDB API keys) are base64url-encoded into the addon URL itself. Each Stremio install has its own URL; the server persists nothing. Container restart, container destroy — doesn't matter, nothing is lost (and nothing can be leaked from disk).
- **No persistent volume.** Torrent pieces live in `/tmp/webtorrent` inside the container. When a torrent is idle for `TORRENT_IDLE_TIMEOUT_MIN` minutes (default 30), it and its downloaded pieces are destroyed.
- **DHT / LSD / µTP all disabled.** DHT/LSD would leak private-tracker infohashes to the public swarm — bannable offence on most trackers. µTP is disabled because `utp-native`'s prebuilt binary segfaults Node.js under load; TCP-only peer connections work fine.
- **Sequential + critical-piece streaming.** WebTorrent v2 removed its `strategy: 'sequential'` option; the replacement is manual: `torrent.files.forEach(f => f.deselect())` → `file.select()` → `torrent.critical(0, 5)`.

### HTTPS without a reverse proxy

Stremio's Windows desktop client rewrites `http://` → `https://` before fetching the manifest, which kills plain-HTTP installs from LAN IPs. The usual answers all have drawbacks:

- Real domain + reverse proxy: overkill for a LAN-only addon
- mkcert + root CA on every Stremio device: painful on TVs
- Self-signed cert: "invalid certificate" popups forever

jackstream bundles a cert + key from [`local-ip.medicmobile.org`](https://local-ip.medicmobile.org) — a community service that:

1. Issues a **publicly-trusted Let's Encrypt wildcard cert** for `*.local-ip.medicmobile.org` (and publishes the private key, by design).
2. Runs a DNS server where `192-168-0-15.local-ip.medicmobile.org` resolves to `192.168.0.15`.

The addon listens on HTTPS 7001 with that cert, and the configure page auto-transforms a LAN IP (e.g. `192.168.0.15`) into the magic hostname (`https://192-168-0-15.local-ip.medicmobile.org:7001`). Browsers and Stremio both see a valid cert; traffic never leaves the LAN. Zero device-side setup.

Tradeoff: anyone with DNS control on the network could MITM (public private key). On a trusted home LAN it's a non-issue. Not suitable for exposing to the public internet — use a real reverse proxy (Caddy/Nginx/Traefik with Let's Encrypt) for that case.

## How to deploy

### 1. Docker Compose

```yaml
jackstream:
  image: lborruto/jackstream:latest
  container_name: jackstream
  ports:
    - 7000:7000   # HTTP (configure page)
    - 7001:7001   # HTTPS (Stremio on LAN devices)
  restart: unless-stopped
```

Multi-arch (amd64 + arm64), so the same image runs on x86 homelabs and Raspberry Pi.

### 2. Open the configure page

From any device on the LAN:

```
http://<server-ip>:7000/configure
```

Fill in:

- **Jackett URL** (e.g. `http://<server-ip>:9117`) and its API key.
- **TMDB API key** (free at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)).
- **Addon public URL / LAN IP** — just the server's LAN IP. The page auto-converts it to the HTTPS hostname.

Use **Test Jackett** / **Test TMDB** to verify credentials live before installing.

### 3. Install in Stremio

Click **Install in Stremio** to launch the native Stremio app with the addon preconfigured. The HTTPS URL is also shown below the button — paste it into Stremio's *Add-on Repository URL* field on clients that don't handle `stremio://` deep links (some Windows builds, most TVs).

For a TV or phone, the least painful path is a Stremio account: install once on desktop while signed in, and the addon syncs to every other signed-in client. No 400-character URL typing on a remote.

### 4. Advanced filters (optional)

Per-user filters that don't require redeploying:

- Preferred audio language (sort boost — doesn't hide non-matches)
- Min / max quality (hard filter)
- Min / max file size (hard filter)
- Blacklist keywords (e.g. `CAM, HDCAM, TELESYNC`)

All filters live in the base64url-encoded URL, so different Stremio installs can use different filter profiles against the same backend.
