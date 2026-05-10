# CLAUDE.md — Confidential Computing Wiki Hub

This repo is a single-repo hub for two mailing list archives, both covering confidential computing:

| List | Source | Data path | Wiki path |
|---|---|---|---|
| **CCC TWI SIG** | groups.io (cookie-auth scrape) | `data/twi/*.md` | `data/twi/wiki/` |
| **linux-coco** | public-inbox mirror at `linux-coco/` | `data/linux-coco/*.md` | `data/linux-coco/wiki/` |

Both are served together by a single `repoview` instance on port 3000, with `data/README.md` as the root landing page.

## Mental model

Scrape → curate → write all wiki pages in one synthesis pass with the `Write` tool directly to the filesystem. There is no llmwiki MCP loop — batch authoring is done by directly writing `.md` files and committing.

One synthesis pass keeps voice, structure, and cross-references coherent across the whole wiki. The `data/README.md` root page links to both list wikis.

## Wiki conventions to follow

- **Layout** under `data/<list>/wiki/`:
  - `overview.md` — hub page; key findings table, source inventory, structural Mermaid diagram, wiki map.
  - `concepts/<topic>.md` — abstract ideas (one file per concept).
  - `entities/{drafts,orgs,people,repos}/<name>.md` — concrete things.
  - `timeline.md` — chronological narrative with a `mermaid timeline` block.
  - `log.md` — append-only record of ingests / lint passes.
- **Frontmatter required** on every page: `title`, `description`, `date` (YYYY-MM-DD), `tags` (≥2).
- **At least one visual element** per page (Mermaid diagram or table). Pages with prose only are incomplete.
- **Citations** as markdown footnotes using the **full source filename** — e.g. `[^src]: 20240508-foo.md`. Don't truncate.
  - Thread files live in `<list>/threads/`. Citation depth: `<list>/*.md` → `threads/THREAD.md`; `<list>/concepts/*.md` → `../threads/THREAD.md`; `<list>/entities/<sub>/*.md` → `../../threads/THREAD.md`
- **Cross-references** with relative markdown links to other wiki pages.
- **Don't write summaries that read like chat replies.** Wiki pages are persistent artifacts — denser and more structured than a conversation answer.

## Repeatable build flow

### TWI SIG (groups.io)

1. **Scrape** — `make scrape-twi`. Idempotent; `data/raw/` cache makes reruns free. Cookie may need refreshing in `.env` if you see 402s.
2. **Read** — filter out agendas/admin noise (~half the corpus). Substantive threads are anything that's *not*: `agenda-for-…`, `meeting-(agenda|minutes)-…`, `no-(twi-)?meeting-…`, `cannot-attend-…`, single-sentence threads.
3. **Write** — `Write` tool directly to `data/twi/wiki/`. Cite every factual claim with the originating thread filename.
4. **Append to `log.md`**, then **commit** (separate commits for raw thread `.md` additions and wiki authoring).

### linux-coco (public-inbox)

1. **Fetch new mail** — `cd linux-coco/git/0.git && git fetch origin`. Incremental; only new commits fetched.
2. **Reindex** — `public-inbox-index ./linux-coco` (updates `linux-coco/xap15/` and `over.sqlite3`).
3. **Scrape** — `make scrape-linux-coco` (uses `scraper/linux-coco/main.py` → reads over.sqlite3 + git blobs → writes `data/linux-coco/*.md`).
4. **Write** — `Write` tool directly to `data/linux-coco/wiki/`. Cite every factual claim.
5. **Append to `log.md`**, then **commit**.

For new corpora, the same flow works — adjust the substantive-thread filter and the wiki structure.

## Operating the stack

### Local dev

```bash
npm install     # install repoview
npm start       # http://localhost:3000 — serves data/ (both wikis + landing page)
```

### Tailnet / LAN exposure

```bash
PORT=3001 npm start   # repoview binds 0.0.0.0 by default
```

## Scraping notes (TWI SIG)

- **Groups.io blocks unauthenticated/non-Chrome traffic** with a 402. We use `curl_cffi` with `impersonate="chrome"` + a logged-in session cookie from `.env` (`GROUPSIO_COOKIE`).
- Cookies expire — when you see `402`, refresh the cookie from a logged-in browser (DevTools → Network → reload `/topics` → copy the `Cookie` header) and rerun.
- `data/raw/` is the response cache (gitignored). `make clean-cache` wipes it.
- `discover_all_topics` walks `/topics?page=N` until a page yields no new topic IDs.

## Scraping notes (linux-coco)

- **Source**: public-inbox git mirror at `linux-coco/git/0.git`. Fetch with `git fetch` inside the bare repo.
- **Extraction**: `scraper/linux-coco/extract.py` queries `linux-coco/xap15/over.sqlite3` for message metadata (subject, from, blob hash, thread ID), then reads email bytes via `git cat-file blob <hash>`.
- `over.sqlite3` computes thread grouping (`tid`) automatically — no need to parse References headers.
- Date range: pass `SINCE` / `UNTIL` to `load_messages()` to extract a time window incrementally.

## Things to *not* do

- Don't batch-write wiki pages using an MCP loop. Use `Write` directly to the filesystem.
- Don't write wiki pages without footnote citations to source filenames.
- Don't commit `linux-coco/` (gitignored, 600MB public-inbox mirror).
