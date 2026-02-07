# Jackett and Byparr in Docker

Jackett translates search queries from Radarr/Sonarr into queries against torrent tracker sites. Byparr handles Cloudflare challenges that would otherwise block Jackett.

## Docker Compose

```yaml
jackett:
  image: lscr.io/linuxserver/jackett:latest
  container_name: jackett
  environment:
    PUID: 1000
    PGID: 1000
    TZ: Europe/Paris
  volumes:
    - /app-config/jackett:/config
  ports:
    - 9117:9117
  restart: unless-stopped

byparr:
  image: ghcr.io/thephaseless/byparr:latest
  container_name: byparr
  environment:
    LOG_LEVEL: info
    LOG_HTML: false
    CAPTCHA_SOLVER: none
    TZ: Europe/Paris
  ports:
    - 8191:8191
  restart: unless-stopped
```

## Web UIs

- Jackett: `http://192.168.0.15:9117`
- Byparr: `http://192.168.0.15:8191` (API only)

## How It Works

1. Radarr/Sonarr send a search query to Jackett via the Torznab API
2. Jackett queries the configured torrent trackers
3. If a tracker uses Cloudflare protection, Jackett routes the request through Byparr (FlareSolverr-compatible API on port 8191)
4. Byparr spins up a headless browser, solves the challenge, and returns the cookies to Jackett
5. Jackett returns the search results to Radarr/Sonarr

## Jackett Configuration

In Jackett's settings, set the FlareSolverr API URL to:

```
http://byparr:8191
```

This works because both containers are on the same Docker network.
