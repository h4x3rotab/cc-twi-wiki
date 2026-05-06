# CLAUDE.md — TWI SIG Wiki

This repo turns the public groups.io archive of the **Confidential Computing TWI SIG** mailing list into a browsable, citation-linked wiki. It vendors [llmwiki](https://github.com/lucasastorian/llmwiki) for the storage / serving layer and a custom scraper for ingest.

The notes below are for Claude (or any agent) working in this repo on a future session.

## Mental model

We use llmwiki as **infrastructure**, not as the authoring framework it was designed to be.

- **llmwiki's intended flow**: point it at a folder, connect Claude over MCP, Claude calls `write` per page over many turns, the SQLite index updates incrementally as the wiki grows.
- **What we do instead**: scrape → curate → write all pages in one synthesis pass with the `Write` tool → `./llmwiki reindex` once. The MCP loop is reserved for *follow-up edits* (answering specific questions, updating after a new scrape, lint passes), not bootstrap.

This is better for batch ingestion because:

- One synthesis pass keeps voice, structure, and cross-references coherent across the whole wiki.
- No per-write tool-call overhead.
- The whole structure (overview → concepts → entities → timeline) can be planned with the corpus in mind, instead of one page at a time.

What we keep from llmwiki: the **structural conventions** (`/wiki/concepts/`, `/wiki/entities/`, frontmatter shape, citation style), the **web UI**, the **search/MCP tools** for later incremental work, and the **SQLite index** built once at the end.

## Wiki conventions to follow

- **Layout** under `data/threads/wiki/`:
  - `overview.md` — hub page; key findings table, source inventory, structural Mermaid diagram, wiki map.
  - `concepts/<topic>.md` — abstract ideas (one file per concept).
  - `entities/{drafts,orgs,people,repos}/<name>.md` — concrete things.
  - `timeline.md` — chronological narrative with a `mermaid timeline` block.
  - `log.md` — append-only record of ingests / lint passes.
- **Frontmatter required** on every page: `title`, `description`, `date` (YYYY-MM-DD), `tags` (≥2).
- **At least one visual element** per page (Mermaid diagram or table). Pages with prose only are incomplete.
- **Citations** as markdown footnotes using the **full source filename** — e.g. `[^src]: 118990275-early-draft-of-the-vienna-submission.md`. Don't truncate.
- **Cross-references** with relative markdown links to other wiki pages.
- **Don't write summaries that read like chat replies.** Wiki pages are persistent artifacts — denser and more structured than a conversation answer.

## Repeatable build flow (the "make wiki" mental model)

This is the workflow to refresh the wiki when the SIG accumulates new threads:

1. **Scrape** — `make scrape`. Idempotent; the cache under `data/raw/` makes reruns free. Cookie may need refreshing in `.env` if you see 402s.
2. **Read** — Read substantive threads in batches by `cat`-ing the markdown files directly. Don't try to read every thread — filter out the agendas-and-admin noise first (~half the corpus is procedural). The substantive threads are listed at the top of each batch read in past sessions; pattern is anything that's *not*: `agenda-for-…`, `meeting-(agenda|minutes)-…`, `no-(twi-)?meeting-…`, `cannot-attend-…`, `please-read-…`, `reminder-to-review-…`, single-sentence threads (`hey.md`, `back.md`).
3. **Plan** — Sketch the new/updated structure: which concept pages need new sections, which entity pages need new dates, what timeline entries to append. Don't reorganise existing pages unless the corpus has materially shifted.
4. **Write** — Use the `Write` tool directly to the filesystem. One synthesis pass. Cite every factual claim with the originating thread filename.
5. **Reindex** — `cd llmwiki && . api/.venv/bin/activate && ./llmwiki reindex ../data/threads`. The SQLite index and reference graph rebuild in seconds.
6. **Append to `log.md`** with the date and a one-line summary per added/updated page.
7. **Commit** — separate commits for `data/threads/*.md` (raw scrape additions) and `data/threads/wiki/**` (wiki authoring), so the diff is readable.

For new corpora that aren't this mailing list, the same flow works — adjust the substantive-thread filter and the wiki structure (concepts/entities is the right backbone for almost any technical-community archive).

## Operating the stack

### Local dev (single user)

```bash
make scrape     # data/threads/<id>-<slug>.md
make build      # ./llmwiki init data/threads
make serve      # http://localhost:3000
```

### Tailnet / LAN exposure

```bash
make serve LLMWIKI_HOST=h4xbox,100.108.169.21,localhost \
           LLMWIKI_PROD=1 \
           LLMWIKI_API_PORT=8001 LLMWIKI_WEB_PORT=3001
```

- `LLMWIKI_PROD=1` is **required** for remote access. `next dev`'s HMR WebSocket assumes the browser hostname matches the bind interface; over a tailnet that's not true and the page comes up blank. The wrapper auto-runs `next build` on first prod start.
- `LLMWIKI_HOST` is comma-separated. The first host wins for `NEXT_PUBLIC_API_URL` (baked into the JS bundle at build time); all hosts are added to the API's CORS allow-origin list. If you change the primary host, you must `rm -rf llmwiki/web/.next` to force a rebuild.
- `LLMWIKI_BIND` is auto-set to `0.0.0.0` whenever any host is non-local; override only if you want to bind to a specific interface.

### Patches we made to vendored llmwiki

- **`llmwiki/llmwiki`**: stale schema path fix (`api/infra/db/sqlite_schema.sql` → `shared/sqlite_schema.sql`); `LLMWIKI_API_PORT` / `LLMWIKI_WEB_PORT` / `LLMWIKI_HOST` / `LLMWIKI_BIND` / `LLMWIKI_PROD` env vars; `cmd_mcp` uses the `mcp/.venv` interpreter and chdirs into `mcp/`.
- **`llmwiki/api/main.py`**: `APP_URL` is parsed as a comma-separated list of CORS origins.
- **`llmwiki/web/package.json`**: both `dev` and `start` scripts include `-H 0.0.0.0`.
- **`llmwiki/api/.venv/`** and **`llmwiki/mcp/.venv/`**: separate venvs because the `mcp[cli]` deps are not in the API requirements. Both are gitignored.

If upstream llmwiki adds these features, prefer to drop our patches.

### MCP

Generate an MCP-server snippet for this workspace with `cd llmwiki && ./llmwiki mcp-config ../data/threads` and register it with whichever MCP client you use (Claude Code: `.mcp.json` at repo root). Use the server for *queries* and *targeted edits* — search, read, and the `guide` tool. Don't loop the MCP `write` tool for batch authoring — see "Mental model" above.

## Scraping notes

- **Groups.io blocks unauthenticated/non-Chrome traffic** with a "Groups.io AI Crawler Policy" 402 page. Firecrawl's chrome-cdp + tlsclient + stealth-proxy engines all fail.
- We use **`curl_cffi` with `impersonate="chrome"` + a logged-in session cookie** from `.env` (`GROUPSIO_COOKIE`). This is the only thing that works.
- Cookies expire — when you see `402` from the scraper, refresh the cookie from a logged-in browser (DevTools → Network → reload `/topics` → copy the `Cookie` header) and rerun.
- One topic page renders the full thread inline as `div.expanded-message` blocks, so we don't need separate `/message/<id>` fetches.
- `data/raw/` is the response cache and is gitignored. `make clean-cache` wipes it; reruns of `make scrape` skip already-fetched URLs.
- `discover_all_topics` walks `/topics?page=N` until a page yields no new topic IDs (groups.io advertises ghost pages in nav past the real last page).

## Things to *not* do

- Don't loop MCP `write` calls for >5 pages of batch authoring. Use `Write` directly + `reindex`.
- Don't commit `data/threads/.llmwiki/` (derived state — gitignored). Do commit `data/threads/wiki/**` (authored content).
- Don't bypass the `next build` step for tailnet exposure. `next dev` will appear to work but show an empty wiki because the HMR WebSocket fails.
- Don't add features to the vendored llmwiki beyond what's needed for tailnet exposure / CLI ergonomics. Track upstream where possible.
- Don't write wiki pages without footnote citations to source filenames. The whole point of the wiki is grounding claims in the corpus.
