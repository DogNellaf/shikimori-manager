# shikimori-manager

> 🇬🇧 English | [🇷🇺 Русский](README_ru.md)

A command-line and web utility that moves **anime and manga** between your [Shikimori](https://shikimori.one) lists according to declarative rules — for example "everything in *Planned* I've already started → *Watching*", or "highly-rated *Dropped* titles → *On hold*".

> ⚠️ Not affiliated with Shikimori. Use at your own risk; always review the dry run before applying.

## Features

- **Anime & manga**: same rules apply to both — episodes for anime, chapters for manga
- **Rule-based**: describe moves as `source → target` with optional conditions on progress, personal score, and community rating
- **Web UI** (Vue 3): RU/EN interface, credential form, one-click auth, list statistics, JSON export, and a live progress bar
- **Safe by default**: previews are dry runs; nothing changes until you apply
- **Polite**: respects Shikimori's rate limits and fetches community scores in batches
- **Self-contained auth**: one-time OAuth, tokens cached and auto-refreshed

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.9+ |
| Frontend | Vue 3 + Vite |
| Auth | Shikimori OAuth 2.0 |
| Config | TOML |

## Requirements

- Python 3.9+
- Node.js 18+ (only for the web UI)
- A Shikimori account

## Installation

```bash
git clone https://github.com/your-username/shikimori-manager
cd shikimori-manager

# CLI only:
python -m pip install -e .

# CLI + web UI:
python -m pip install -e ".[web]"
```

This installs a `shikimori-manager` command (also runnable as `python -m shikimori_manager`).

## Setup

### 1. Register a Shikimori OAuth application

1. Open <https://shikimori.one/oauth/applications> and create an application.
2. Set **Redirect URI** to `urn:ietf:wg:oauth:2.0:oob`.
3. Set **Scopes** to `user_rates` (and `user`).
4. Copy the **Client ID** and **Client Secret**.

### 2. Configure credentials

```bash
cp config.example.toml config.toml   # fill in client_id / client_secret
shikimori-manager auth                # open URL, paste code (one time)
```

Alternatively, use environment variables instead of a config file:

| Variable | Description |
|---|---|
| `SHIKI_CLIENT_ID` | OAuth application Client ID |
| `SHIKI_CLIENT_SECRET` | OAuth application Client Secret |
| `SHIKI_USER` | Your Shikimori username |
| `SHIKI_USER_AGENT` | Custom User-Agent string |

## Usage

### Web UI (recommended)

```bash
# Build the frontend once
cd web && npm install && npm run build && cd ..

# Launch the server
shikimori-manager serve   # http://127.0.0.1:8000
```

1. **Settings & Auth** tab → enter Client ID and Client Secret → *Save settings*
2. Click **Open authorization page**, approve access, paste the one-time code → **Submit code**
3. **Dashboard** tab → *Load statistics* or *Export all to JSON*
4. **Rule mover** tab → add rules or pick a preset → **Preview (dry run)** → **Apply**

For frontend development with hot reload:

```bash
shikimori-manager serve    # terminal 1 — API on :8000
cd web && npm run dev      # terminal 2 → http://localhost:5173
```

### CLI

```bash
shikimori-manager whoami                   # check auth
shikimori-manager lists                    # entries per list
shikimori-manager stats                    # count / episodes / avg score per list
shikimori-manager export -o backup.json    # back up all lists to JSON
shikimori-manager run                      # dry run: preview the moves
shikimori-manager run --apply              # perform the moves
```

Common `run` flags:

| Flag | Meaning |
|---|---|
| `-c, --config PATH` | Use a different config file (default `config.toml`) |
| `--apply` | Perform the moves (otherwise dry run) |
| `--verbose` | List every planned move instead of a sample |
| `--sample N` | How many moves to preview in a dry run (default 20) |

## Writing Rules

A rule moves entries from a `source` list to a `target` list for a given `media` (**anime** or **manga**) when its conditions hold. Rules are evaluated **top-to-bottom per (media, source)** — the **first matching rule wins**, so order matters.

Statuses: `planned`, `watching`, `rewatching`, `completed`, `on_hold`, `dropped`.

```toml
[[rules]]
name = "started -> watching"   # optional label
media = "anime"                # "anime" (default) or "manga"
source = "planned"             # required
target = "watching"            # required
min_episodes = 1               # conditions are optional
```

### Conditions

All conditions are optional and use **inclusive** bounds.

| Condition | Keys | Aliases | Meaning |
|---|---|---|---|
| Progress | `min_progress` / `max_progress` | `min_episodes`, `min_chapters`, … | Episodes watched or chapters read |
| Personal score | `min_score` / `max_score` | — | Your score on the entry (0 = not rated) |
| Community rating | `min_rating` / `max_rating` | `min_anime_score`, `min_manga_score`, … | Title's community score on Shikimori |

Ratings are floats (e.g. `8.38`). To express *strictly greater than 8*, use `min_rating = 8.01`.

### Examples

```toml
# Anime "Planned": started → watching; untouched, high-rated → on hold
[[rules]]
media = "anime"
source = "planned"
target = "watching"
min_episodes = 1

[[rules]]
media = "anime"
source = "planned"
target = "on_hold"
max_episodes = 0
min_rating = 8.01

# Manga "Dropped": unread, highly rated → on hold; the rest → planned
[[rules]]
media = "manga"
source = "dropped"
target = "on_hold"
max_score = 0
max_chapters = 0
min_rating = 8.01

[[rules]]
media = "manga"
source = "dropped"
target = "planned"
max_score = 0
max_chapters = 0
```

## Project Structure

```
shikimori-manager/
├── shikimori_manager/   # Core Python package (auth, API client, rule engine)
├── web/                 # Vue 3 frontend (Vite)
├── config.example.toml  # Config template
├── pyproject.toml
└── LICENSE
```

## Security

`config.toml`, `.env*`, and `.token.json` hold secrets and are gitignored. Never commit them. If a `client_secret` or token leaks, rotate it in your Shikimori app settings.

## License

[MIT](LICENSE)
