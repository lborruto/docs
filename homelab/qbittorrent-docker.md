# qBittorrent in Docker

Download client for the *arr stack. Radarr and Sonarr send downloads here.

## Docker Compose

```yaml
qbittorrent:
  image: lscr.io/linuxserver/qbittorrent:latest
  container_name: qbittorrent
  environment:
    PUID: 1000
    PGID: 1000
    TZ: Europe/Paris
    WEBUI_PORT: 8080
  volumes:
    - /app-config/qbittorrent/config:/config
    - /data:/downloads
    - /data:/data
  ports:
    - 8080:8080
    - 6881:6881
    - 6881:6881/udp
  restart: unless-stopped
```

## Web UI

`http://homelab.local:8080`

Default credentials on first launch are printed in the container logs (`docker logs qbittorrent`).

## Ports

- **8080** -- Web UI
- **6881 TCP/UDP** -- BitTorrent listening port for incoming peer connections

## Downloads Path

Downloads go to `/data/torrents/downloads/`. Radarr and Sonarr pick them up from there and hardlink into `/data/media/`.
