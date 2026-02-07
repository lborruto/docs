# Dispatcharr in Docker

Dispatcharr manages IPTV streams -- it acts as a middleware between IPTV providers and Plex/media players, handling stream routing and channel management.

## Docker Compose

```yaml
dispatcharr:
  image: ghcr.io/dispatcharr/dispatcharr:latest
  container_name: dispatcharr
  environment:
    DISPATCHARR_ENV: aio
    REDIS_HOST: localhost
    CELERY_BROKER_URL: redis://localhost:6379/0
    DISPATCHARR_LOG_LEVEL: info
    TZ: Europe/Paris
  volumes:
    - dispatcharr_data:/data
  ports:
    - 9191:9191
  devices:
    - /dev/dri:/dev/dri
  restart: unless-stopped
```

## Web UI

`http://homelab.internal:9191`

## Key Configuration

- **`DISPATCHARR_ENV: aio`** -- all-in-one mode, runs Redis and Celery worker inside the same container (no need for separate Redis/Celery containers)
- **`/dev/dri:/dev/dri`** -- GPU passthrough for hardware-accelerated stream transcoding
- **Named volume `dispatcharr_data`** -- uses a Docker-managed volume instead of a bind mount for its data

## Client Setup with TiviMate

We use [TiviMate](https://tivimate.com/) as the IPTV client (Android/Fire TV). Dispatcharr exposes an **Xtream Codes API** endpoint specifically for this -- configure TiviMate with the Xtream Codes connection type and point it at Dispatcharr's URL.

This works for both **TV** and **VOD** content.

## Managing Groups

It's recommended to manage channel/VOD groups in Dispatcharr's web UI before connecting clients. By default, IPTV providers load channels from all countries and categories. Disabling the groups you don't need:

- Speeds up EPG (Electronic Program Guide) loading significantly
- Reduces VOD catalog load time
- Makes TiviMate much snappier to browse

Go to the Dispatcharr web UI, filter by groups, and only enable the ones you actually watch.
