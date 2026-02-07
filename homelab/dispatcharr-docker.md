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

`http://homelab.local:9191`

## Key Configuration

- **`DISPATCHARR_ENV: aio`** -- all-in-one mode, runs Redis and Celery worker inside the same container (no need for separate Redis/Celery containers)
- **`/dev/dri:/dev/dri`** -- GPU passthrough for hardware-accelerated stream transcoding
- **Named volume `dispatcharr_data`** -- uses a Docker-managed volume instead of a bind mount for its data
