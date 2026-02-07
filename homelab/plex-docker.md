# Plex Media Server in Docker

Running Plex with hardware transcoding via Intel Quick Sync on my home server.

## Docker Compose

```yaml
plex:
  image: lscr.io/linuxserver/plex:latest
  container_name: plex
  network_mode: host
  environment:
    PUID: 1000
    PGID: 1000
    TZ: Europe/Paris
    VERSION: docker
  devices:
    - /dev/dri:/dev/dri
  volumes:
    - /app-config/plex:/config
    - /data:/data
  restart: unless-stopped
```

## Key Decisions

- **`network_mode: host`** -- required for DLNA discovery and local streaming to work without hassle. Plex uses a lot of random ports for local device discovery.
- **`/dev/dri:/dev/dri`** -- passes through the Intel integrated GPU for hardware transcoding. Without this, Plex falls back to software transcoding which maxes out the i3 quickly.
- **Single `/data` mount** -- Plex sees `/data/media/movies` and `/data/media/tv`. This is the same mount Radarr/Sonarr use, so hardlinks work (no duplicate disk usage).

## Media Library Structure

```
/data/media/
  movies/
  tv/
```

Plex libraries are pointed at `/data/media/movies` and `/data/media/tv`.

## Monitoring

Tautulli runs alongside Plex for viewing stats and history -- see the [Tautulli TIL](tautulli-docker.md).
