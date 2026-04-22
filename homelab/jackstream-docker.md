# jackstream in Docker

Self-hosted Stremio addon that queries my Jackett and streams torrents via an embedded WebTorrent client. No debrid, no qBittorrent, no shared volume. One container.

Source: <https://github.com/lborruto/jackstream>

## Why build this

My Plex + Radarr / Sonarr stack downloads what I know I want. For everything else I wanted torrent streaming **directly inside Stremio**, on any device on the LAN, without:

- Debrid accounts ($)
- qBittorrent running alongside (needs a shared volume for the `.torrent` download path)
- Rewriting trackers for each addon

jackstream takes the IMDB id Stremio sends, asks my Jackett for torrents, and streams them via WebTorrent. Because Jackett proxies the `.torrent` URL (with passkeys for private trackers already embedded in the announce URLs), WebTorrent can connect to private trackers out of the box — no cookies or credentials to juggle.

## Docker Compose

```yaml
jackstream:
  image: lborruto/jackstream:latest
  container_name: jackstream
  ports:
    - 7000:7000   # HTTP (configure page)
    - 7001:7001   # HTTPS (Stremio on LAN devices)
  restart: unless-stopped
```

Then open `http://<server-ip>:7000/configure`, paste in my Jackett URL + API key, a free TMDB API key, and the server's LAN IP. The install button generates a `stremio://` deep link that launches the native Stremio app.

## The HTTPS problem — and solution

Stremio's Windows desktop client rewrites `http://` → `https://` before fetching the manifest, which kills plain-HTTP installs from LAN IPs. Options are all bad:

- Real domain + reverse proxy: overkill for a LAN-only addon
- mkcert + root CA on every Stremio device: painful on TVs
- Self-signed cert: "invalid certificate" popups forever

The trick I borrowed from [`nyakaspeter/stremio-torrent-stream`](https://github.com/nyakaspeter/stremio-torrent-stream) is [`local-ip.medicmobile.org`](https://local-ip.medicmobile.org) — a community service that:

1. Issues a **publicly-trusted Let's Encrypt wildcard cert** for `*.local-ip.medicmobile.org` (and publishes the private key, by design).
2. Runs a DNS server where `192-168-0-15.local-ip.medicmobile.org` resolves to `192.168.0.15`.

So I bundle the cert + key in the Docker image, listen on 7001 with HTTPS, and the configure page auto-transforms my LAN IP into the magic hostname. Browsers and Stremio both see a valid cert, traffic never leaves the LAN. Zero device-side setup.

Tradeoff: anyone with DNS control on my network could MITM (public private key). On a trusted home LAN it's a non-issue. Not suitable for exposing to the internet.

## Key architectural choices

- **Zero server-side storage.** Credentials (Jackett + TMDB keys) are base64url-encoded into the addon URL. Each Stremio install has its own URL; the server stores nothing.
- **No persistent volume.** Torrents live in `/tmp/webtorrent` inside the container. When a torrent is idle for `TORRENT_IDLE_TIMEOUT_MIN` (30 min default), it and its downloaded pieces are destroyed.
- **DHT / LSD / µTP all disabled.** DHT would leak private-tracker infohashes to the public swarm. µTP is disabled because `utp-native` was segfaulting the Node.js process — TCP-only peer connections work fine for private trackers.
- **Sequential + critical-piece streaming.** WebTorrent v2 removed its `strategy: 'sequential'` option; the replacement is manual: `torrent.files.forEach(f => f.deselect())` → `file.select()` → `torrent.critical(0, 5)`.

## Gotchas I hit

- **QEMU cross-build from an M-series Mac ran fine** for amd64, but any native module segfault on the target would have been mistaken for a "cross-build bug". Disabling µTP was the real fix — `utp-native`'s prebuilt linux-x64 binary crashes under load.
- **Exit code 139 = SIGSEGV.** With `restart: unless-stopped`, the container auto-restarted on crash, which wiped the in-memory torrent store, which surfaced as "Stream session expired" on the user side. The root cause was invisible until I pulled `docker events`.
- **Stremio's `stremio://host:port/...` deep link.** Some clients handle the port, some strip it. Configure page shows the HTTPS URL as a paste-fallback so I can always manually add it in Stremio's "Add-on Repository URL" field.
- **Stremio Web (`web.stremio.com`) won't load plain-HTTP addons** due to mixed-content rules. Only a problem if I use the web client — native Stremio apps are fine on HTTP for localhost, and HTTPS (via the trick above) for LAN IPs.

## How I configured it

```
Jackett URL:      http://<server-ip>:9117
Jackett API key:  <from Jackett settings page>
TMDB API key:     <free from themoviedb.org/settings/api>
Addon LAN IP:     <my server's LAN IP>
Advanced filters: preferred language = FRENCH, blacklist = CAM, HDCAM, TELESYNC
```

The form persists in `localStorage`, so reloading `/configure` repopulates everything.

## Syncing to LG TV

Typing a 400-character URL on a TV remote is cruel. Stremio has cloud sync — installing the addon once on desktop while signed in to a Stremio account pushes it to every other device signed in to that account, including the TV. Zero typing.
