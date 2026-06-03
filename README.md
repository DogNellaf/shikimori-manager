# shikimori-manager

*Languages: **English** · [Русский](README.ru.md)*

A command-line **and web** utility that moves **anime and manga** between your
[Shikimori](https://shikimori.one) lists according to **declarative rules** —
for example "everything in *Planned* I've already started → *Watching*", or
"highly-rated *Dropped* titles → *On hold*".

- **Anime & manga**: same rules apply to both (they share the same structure on
  Shikimori — episodes for anime, chapters for manga).
- **Rule-based**: describe moves as `source → target` with optional conditions
  on progress, your personal score, and the title's community rating.
- **Web UI** (Vue 3): RU/EN interface, credential form, one-click auth, list
  statistics, JSON export, and a rule mover with a live **progress bar**.
- **Safe by default**: previews are dry runs; nothing changes until you apply.
- **Polite**: respects Shikimori's rate limits and fetches community scores in
  batches.
- **Self-contained auth**: one-time OAuth, tokens cached and auto-refreshed.

> ⚠️ Not affiliated with Shikimori. Use at your own risk; always review the dry
> run before applying.

---

## Requirements

- Python 3.9+
- Node.js 18+ (only if you want the web UI)
- A Shikimori account

---

## 1. Register a Shikimori OAuth application

1. Open <https://shikimori.one/oauth/applications> and create an application.
2. Set **Redirect URI** to `urn:ietf:wg:oauth:2.0:oob`.
3. Set **Scopes** to `user_rates` (and `user`).
4. Copy the **Client ID** and **Client Secret** — you'll need them next.

---

## 2. Install

```bash
git clone https://github.com/your-username/shikimori-manager
cd shikimori-manager

# CLI only:
python -m pip install -e .

# ...or CLI + web UI:
python -m pip install -e ".[web]"
```

This installs a `shikimori-manager` command (also runnable as
`python -m shikimori_manager`).

---

## 3a. Use the Web UI (recommended)

```bash
# build the frontend once
cd web && npm install && npm run build && cd ..

# launch the server
shikimori-manager serve            # http://127.0.0.1:8000
```

Then, in the browser:

1. Switch language with the **RU/EN** button (top-right) if you like.
2. **Settings & Auth** tab → enter **Client ID** and **Client Secret** →
   *Save settings*. (Stored in a gitignored `.env`.)
3. Click **Open authorization page**, approve access, copy the one-time code
   (valid ~2 minutes), paste it, and **Submit code**. The token is cached in
   `.token.json` and refreshed automatically afterwards.
4. **Dashboard** tab → *Load statistics* (counts, episodes, average score),
   or *Export all to JSON* for a backup.
5. **Rule mover** tab → add rules or use a preset, **Preview (dry run)** to see
   what would move (with a progress bar), then **Apply**.

### Frontend development (hot reload)

```bash
shikimori-manager serve            # terminal 1 (API on :8000)
cd web && npm run dev            # terminal 2 -> http://localhost:5173
```

The server binds to `127.0.0.1` by default — it's a local tool and shouldn't be
exposed to the network.

---

## 3b. Use the CLI

```bash
cp config.example.toml config.toml      # then fill in client_id / client_secret
shikimori-manager auth                     # open URL, paste code (one time)

shikimori-manager whoami                   # check auth
shikimori-manager lists                    # entries per list
shikimori-manager stats                    # count / episodes / avg score per list
shikimori-manager export -o backup.json    # back up all lists to JSON
shikimori-manager run                      # dry run: preview the moves
shikimori-manager run --apply              # perform the moves
```

You can also provide credentials via environment variables instead of the
config file: `SHIKI_CLIENT_ID`, `SHIKI_CLIENT_SECRET`, `SHIKI_USER`,
`SHIKI_USER_AGENT`.

Common `run` flags:

| Flag | Meaning |
| --- | --- |
| `-c, --config PATH` | Use a different config file (default `config.toml`). |
| `--apply` | Perform the moves (otherwise dry run). |
| `--verbose` | List every planned move instead of a sample. |
| `--sample N` | How many moves to preview in a dry run (default 20). |

---

## Writing rules

A rule moves entries from a `source` list to a `target` list, for a given
`media` (**anime** or **manga**), when its conditions hold. Rules are evaluated
**top-to-bottom per (media, source)**, and the **first matching rule wins** — so
order matters.

Anime and manga have the same structure on Shikimori, so the same conditions
apply to both — only `media` differs.

In the CLI, rules live in `config.toml`:

```toml
[[rules]]
name = "started -> watching"   # optional label
media = "anime"                # "anime" (default) or "manga"
source = "planned"             # required
target = "watching"            # required
min_episodes = 1               # condition(s) below are optional
```

In the web UI you build the same rules with form fields (with a media selector
and two presets).

Statuses: `planned`, `watching`, `rewatching`, `completed`, `on_hold`,
`dropped`.

### Conditions

All conditions are optional and use **inclusive** bounds. They're media-neutral,
with friendly aliases.

| Condition | Canonical keys | Aliases | Meaning |
| --- | --- | --- | --- |
| Progress | `min_progress` / `max_progress` | `min_episodes`/`max_episodes`, `min_chapters`/`max_chapters` | Episodes watched (anime) or chapters read (manga). |
| Personal score | `min_score` / `max_score` | — | Your score on the entry (0 = not rated). |
| Community rating | `min_rating` / `max_rating` | `min_anime_score`/`max_anime_score`, `min_manga_score`/`max_manga_score` | The title's community score on Shikimori. |

Ratings are floats (e.g. `8.38`). To express *strictly greater than 8*, use
`min_rating = 8.01`. Ratings are only fetched for entries that actually reach a
rating condition, so rating-free rules cost no extra requests.

### Example: tidy up anime "Planned"

```toml
# Anything I've started watching becomes "watching" (checked first → wins).
[[rules]]
media = "anime"
source = "planned"
target = "watching"
min_episodes = 1

# Otherwise, untouched titles rated above 8 go to "on hold".
[[rules]]
media = "anime"
source = "planned"
target = "on_hold"
max_episodes = 0
min_rating = 8.01
```

### Example: clean out manga "Dropped"

```toml
# Unrated, never-read manga with a great community rating -> on hold.
[[rules]]
media = "manga"
source = "dropped"
target = "on_hold"
max_score = 0
max_chapters = 0
min_rating = 8.01

# The rest of those unrated, never-read drops -> planned.
[[rules]]
media = "manga"
source = "dropped"
target = "planned"
max_score = 0
max_chapters = 0
```

---

## How it works

- Lists are read via `GET /api/v2/user_rates` (with `target_type=Anime|Manga`).
  That endpoint can ignore `limit`/`page` and return the whole list on every
  page, so the client stops paginating once a page yields no new ids (instead of
  looping forever).
- Community ratings come from `GET /api/animes?ids=...` / `GET /api/mangas?ids=...`
  in batches of 50.
- Moves are `PATCH /api/v2/user_rates/:id` with the new status.
- In the web UI, a move runs as a background job; the UI polls its progress and
  renders the bar.
- All requests send the required `User-Agent` and back off on HTTP 429.

## Security

`config.toml`, `.env*` and `.token.json` hold secrets and are gitignored. Never
commit them. If a `client_secret` or token leaks, rotate it in your Shikimori
app settings.

## License

[MIT](LICENSE)
