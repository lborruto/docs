# Watchtower in Docker

Watchtower automatically updates all running containers to their latest images. No more manual `docker compose pull && docker compose up -d`.

## Docker Compose

```yaml
watchtower:
  image: containrrr/watchtower:latest
  container_name: watchtower
  environment:
    WATCHTOWER_CLEANUP: "true"
    WATCHTOWER_SCHEDULE: "0 0 2 * * *"
    TZ: Europe/Paris
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
  restart: unless-stopped
```

## How It Works

- **Schedule:** Runs daily at 02:00 (`0 0 2 * * *` is cron for 2 AM)
- **Cleanup:** `WATCHTOWER_CLEANUP: true` removes old images after updating, saving disk space
- **Docker socket:** Needs `/var/run/docker.sock` to talk to the Docker daemon and manage containers

Watchtower checks every running container, pulls the latest image, and recreates the container with the same configuration if the image has changed. All other containers see zero-downtime updates since Watchtower restarts them one at a time.
