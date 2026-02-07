# Radarr and Sonarr in Docker

Radarr manages movies, Sonarr manages TV shows. Both follow the same pattern -- they monitor for wanted media, send download requests to qBittorrent, and organize files into the Plex library.

## Docker Compose

```yaml
radarr:
  image: lscr.io/linuxserver/radarr:latest
  container_name: radarr
  environment:
    PUID: 1000
    PGID: 1000
    TZ: Europe/Paris
  volumes:
    - /app-config/radarr/config:/config
    - /data:/data
  ports:
    - 7878:7878
  restart: unless-stopped

sonarr:
  image: lscr.io/linuxserver/sonarr:latest
  container_name: sonarr
  environment:
    PUID: 1000
    PGID: 1000
    TZ: Europe/Paris
  volumes:
    - /app-config/sonarr/config:/config
    - /data:/data
  ports:
    - 8989:8989
  restart: unless-stopped
```

## Web UIs

- Radarr: `http://192.168.0.15:7878`
- Sonarr: `http://192.168.0.15:8989`

## The `/data` Volume Trick

Both containers mount `/data` at `/data` -- the same path as qBittorrent and Plex. This means:

1. qBittorrent downloads to `/data/torrents/downloads/`
2. Radarr/Sonarr create a **hardlink** from `/data/torrents/downloads/file.mkv` to `/data/media/movies/file.mkv`
3. No extra disk space used, no slow copy/move operations

This only works because all containers share the same `/data` mount at the same path. If they used different paths (e.g. `/movies` in one and `/downloads` in another), hardlinks wouldn't work and files would be copied instead.

## Integration

- **Download client:** qBittorrent (port 8080)
- **Indexers:** Jackett (port 9117), configured as Torznab indexers in both Radarr and Sonarr
- **Media server:** Plex picks up organized files automatically from `/data/media/`
