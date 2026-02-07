# Today I Learned

A collection of concise write-ups on small things I learn day to day. Powered by [Datasette](https://datasette.io/) and deployed automatically via GitHub Actions.

<!-- count starts -->0<!-- count ends --> TILs so far. <a href="https://til.simonwillison.net/til/feed.atom">Atom feed here</a>.

<!-- index starts -->
<!-- index ends -->

---

## How It Works

This repository is a self-updating TIL (Today I Learned) system:

1. **You write** a short Markdown file in a topic folder (e.g. `python/my-trick.md`).
2. **On push to `main`**, a GitHub Actions workflow runs automatically:
   - `build_database.py` scans all `*/*.md` files and builds a SQLite database (`tils.db`) with full-text search.
   - Markdown is rendered to HTML using the GitHub Markdown API.
   - Git history is used to extract created/updated timestamps for each file (follows renames).
   - `update_readme.py` regenerates this README with an indexed list of all TILs.
   - `generate_screenshots.py` creates social-media preview images for each TIL.
3. **The database is deployed** as a searchable website using Datasette, with custom templates, plugins, Atom feeds, and a GraphQL API.

### Architecture

```
topic-folder/my-til.md   -->  build_database.py  -->  tils.db (SQLite)
                                                         |
                                                   update_readme.py --> README.md
                                                         |
                                                   Datasette deploy --> live website
```

### Key Components

| File | Purpose |
|---|---|
| `build_database.py` | Scans `*/*.md` files, renders Markdown via GitHub API, stores in SQLite |
| `update_readme.py` | Regenerates README index from the database |
| `generate_screenshots.py` | Creates social-media preview images (stored in S3) |
| `metadata.yaml` | Datasette configuration: title, feeds, search queries, plugins |
| `requirements.txt` | Python dependencies |
| `templates/` | Custom Datasette HTML templates (homepage, search, topic pages) |
| `plugins/` | Custom Datasette plugins (redirects, template helpers) |
| `static/` | Static assets served by Datasette |

---

## How to Deploy

### Prerequisites

- Python 3.11+
- A GitHub repository with Actions enabled
- A deployment target (see options below)

### 1. Add Your First TIL

Create a topic folder and a Markdown file:

```
mkdir python
echo "# My First TIL\n\nSomething I learned today." > python/my-first-til.md
```

### 2. Configure the Workflow

The workflow lives at `.github/workflows/build.yml`. The current workflow deploys to **Fly.io** and uses **AWS S3** for storage. You will need to adapt it based on your deployment target.

#### GitHub Secrets Required

| Secret | Purpose |
|---|---|
| `GITHUB_TOKEN` | Provided automatically by GitHub Actions. Used to render Markdown via GitHub API. |

Depending on your deployment target, you may also need:

| Secret | Purpose |
|---|---|
| `AWS_ACCESS_KEY_ID` | S3 access for screenshots and database backup |
| `AWS_SECRET_ACCESS_KEY` | S3 secret key |
| `FLY_TOKEN` | Fly.io deployment token |

### 3. Deployment Options

#### Option A: GitHub Pages (simplest)

To deploy as a static site on GitHub Pages, you would need to replace the Fly.io deployment step with a static site export. The current setup is designed for a dynamic Datasette server, not static hosting. To use GitHub Pages:

1. Replace the Fly.io deploy step in `.github/workflows/build.yml` with a step that exports static HTML.
2. Enable GitHub Pages in your repository settings (Settings > Pages > Source: GitHub Actions).
3. Use a `datasette` export or a static site generator to produce HTML from the database.

#### Option B: Fly.io (current setup)

1. Install the [Fly.io CLI](https://fly.io/docs/hands-on/install-flyctl/) and create an account.
2. Run `fly apps create your-app-name`.
3. Add `FLY_TOKEN` to your GitHub repository secrets.
4. Update the `--app` name in `.github/workflows/build.yml`.

#### Option C: Other Platforms

Datasette supports publishing to multiple platforms:
- `datasette publish cloudrun` -- Google Cloud Run
- `datasette publish heroku` -- Heroku
- `datasette publish vercel` -- Vercel

See the [Datasette publishing docs](https://docs.datasette.io/en/stable/publish.html) for details.

### 4. Customization

- **`metadata.yaml`**: Change the site title, about URL, and plugin settings.
- **`templates/`**: Customize the look and feel of the website.
- **`build_database.py` line 53**: Update the GitHub URL to point to your own repository.
- **`plugins/`**: Add or modify Datasette plugin hooks.

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
