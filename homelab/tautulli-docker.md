# Tautulli in Docker

Tautulli monitors Plex -- who's watching what, transcoding stats, history, and notifications.

## Docker Compose

```yaml
tautulli:
  image: lscr.io/linuxserver/tautulli:latest
  container_name: tautulli
  environment:
    PUID: 1000
    PGID: 1000
    TZ: Europe/Paris
  volumes:
    - /app-config/tautulli:/config
  ports:
    - 8181:8181
  restart: unless-stopped
```

## Web UI

`http://homelab.local:8181`

## Setup

On first launch, point Tautulli at the Plex server. Since Plex runs with `network_mode: host`, use the host IP:

```
http://homelab.local:32400
```

You'll need a Plex token -- Tautulli's setup wizard walks you through getting one.
