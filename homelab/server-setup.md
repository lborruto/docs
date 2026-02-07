# Home Server Setup

My home server running all my self-hosted services.

## Hardware

- **CPU:** Intel Core i3-3220 @ 3.30GHz (4 cores)
- **RAM:** 12GB
- **Storage:** 1.8TB (single drive, `/dev/sda1`)
- **GPU:** Intel integrated (passed through to containers via `/dev/dri` for hardware transcoding)

## OS

Debian 12 (Bookworm), kernel 6.1.0-41-amd64.

## Directory Layout

```
/app-config/                  # All container configs
  docker-compose.yaml         # Single compose file for everything
  jackett/
  plex/
  qbittorrent/
  radarr/
  sonarr/
  tautulli/
  adguardhome/
  adguardhome/

/data/                        # All media and downloads
  media/
    movies/
    tv/
  torrents/
    downloads/
```

All services run from a single `docker-compose.yaml` in `/app-config/`. Everything uses `PUID=1000` / `PGID=1000` and `TZ=Europe/Paris`.

## Network

- **LAN IP:** `192.168.0.15`
- **Local hostname:** `homelab.internal` (via AdGuard Home DNS rewrite)
- **Remote access:** Twingate connector (zero-trust, no port forwarding needed)
- **DNS:** AdGuard Home on port 53, with web UI on port 3000

## Maintenance

[Watchtower](https://containrrr.dev/watchtower/) auto-updates all containers daily at 02:00 and cleans up old images.

### Cronitor Jobs

Two scripts monitored by [Cronitor](https://cronitor.io/):

- **`/usr/local/bin/disk_full.sh`** -- if `/dev/sda1` goes above 90% capacity, clears `/data/torrents/downloads/` and restarts qBittorrent
- **`/usr/local/bin/check.sh`** -- heartbeat ping to confirm the server is alive


## Running Services

| Service | Port | Purpose |
|---|---|---|
| Plex | host network | Media server |
| qBittorrent | 8080 | Download client |
| Radarr | 7878 | Movie management |
| Sonarr | 8989 | TV show management |
| Jackett | 9117 | Torrent indexer proxy |
| Byparr | 8191 | Cloudflare bypass for Jackett |
| Tautulli | 8181 | Plex monitoring/stats |
| Dispatcharr | 9191 | IPTV management |
| AdGuard Home | 53, 80, 3000 | Network-wide DNS ad blocking |
| Watchtower | -- | Auto-update containers |
| Twingate | -- | Remote access connector |
