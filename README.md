# Today I Learned

A collection of concise write-ups on small things I learn day to day. Powered by [Datasette](https://datasette.io/) and deployed automatically to [Fly.io](https://fly.io/) via GitHub Actions.

Search these TILs at https://docs.luca-borruto.com/

<!-- count starts -->11<!-- count ends --> TILs so far. <a href="https://docs.luca-borruto.com/tils/feed.atom">Atom feed here</a>.

<!-- index starts -->
## llms

* [Running OpenClaw in Docker](https://github.com/lborruto/docs/blob/main/llms/openclaw-docker.md) - 2026-02-01

## homelab

* [Radarr and Sonarr in Docker](https://github.com/lborruto/docs/blob/main/homelab/radarr-sonarr-docker.md) - 2026-02-07
* [Plex Media Server in Docker](https://github.com/lborruto/docs/blob/main/homelab/plex-docker.md) - 2026-02-07
* [Tautulli in Docker](https://github.com/lborruto/docs/blob/main/homelab/tautulli-docker.md) - 2026-02-07
* [Home Server Setup](https://github.com/lborruto/docs/blob/main/homelab/server-setup.md) - 2026-02-07
* [Watchtower in Docker](https://github.com/lborruto/docs/blob/main/homelab/watchtower-docker.md) - 2026-02-07
* [Twingate in Docker](https://github.com/lborruto/docs/blob/main/homelab/twingate-docker.md) - 2026-02-07
* [Jackett and Byparr in Docker](https://github.com/lborruto/docs/blob/main/homelab/jackett-byparr-docker.md) - 2026-02-07
* [qBittorrent in Docker](https://github.com/lborruto/docs/blob/main/homelab/qbittorrent-docker.md) - 2026-02-07
* [AdGuard Home in Docker](https://github.com/lborruto/docs/blob/main/homelab/adguard-home-docker.md) - 2026-02-07
* [Dispatcharr in Docker](https://github.com/lborruto/docs/blob/main/homelab/dispatcharr-docker.md) - 2026-02-07
<!-- index ends -->

---

## How It Works

1. **Write** a Markdown file in a topic folder (e.g. `python/my-trick.md`).
2. **Push to `main`** -- GitHub Actions builds a SQLite database, updates this README, and deploys a Datasette instance to Fly.io.
3. **Browse** the live site with full-text search, topic browsing, Atom feeds, and a GraphQL API.

### Key Components

| File | Purpose |
|---|---|
| `build_database.py` | Scans `*/*.md` files, renders Markdown via GitHub API, stores in SQLite |
| `update_readme.py` | Regenerates README index from the database |
| `metadata.yaml` | Datasette configuration: title, feeds, search queries, plugins |
| `templates/` | Custom Datasette HTML templates |
| `plugins/` | Custom Datasette plugins |

---

## Setup

### Prerequisites

- A [Fly.io](https://fly.io/) account (free tier works)
- The [Fly CLI](https://fly.io/docs/hands-on/install-flyctl/) installed

### Deploy

1. Create a Fly app:
   ```bash
   fly apps create your-app-name
   ```
2. Get a deploy token:
   ```bash
   fly tokens create deploy -a your-app-name
   ```
3. Add these to your GitHub repo:
   - **Secret** `FLY_TOKEN` -- the deploy token from step 2
   - **Variable** `FLY_APP_NAME` -- your app name from step 1
   (Settings > Secrets and variables > Actions)
4. Push to `main` -- the workflow handles the rest.

### Custom Domain

To point `docs.yourdomain.com` at your Fly app:

1. Add a CNAME in your DNS: `docs` -> `your-app-name.fly.dev.`
2. Add the certificate in Fly:
   ```bash
   fly certs create docs.yourdomain.com -a your-app-name
   ```

---

## How to Write a TIL

Each TIL is a [GitHub-Flavored Markdown](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax) file inside a topic folder:

```
topic-name/my-til-title.md
```

The folder name becomes the **topic**, the filename (minus `.md`) becomes the **slug**.

The only requirement is that the file starts with a `# Title` on the first line -- this is extracted as the TIL title. Everything after it is the body.

```markdown
# Title of Your TIL

Content goes here.
```

### Tips

- Keep TILs short and focused on a single concept.
- Use descriptive filenames with hyphens: `parsing-json-with-jq.md`.
- Use lowercase for topic folder names: `python/`, `github-actions/`, `docker/`.
- The first paragraph is used as the summary/preview on the website.
- Dates are extracted automatically from git history -- no need to add them manually.
