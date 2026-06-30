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

1. **Refresh cookie if needed** — `make scrape-twi` will produce `found 0 topics` if the Spur MCL bot detection blocks it (see scraping notes below). Refresh cookie using Chrome MCP: navigate to `https://lists.confidentialcomputing.io/login` → authenticates via Linux Foundation SSO → navigate to TWI SIG topics page → capture `Cookie:` header from a network request → update `.env`.
2. **Discover new topics via browser** — Bot detection blocks the `/topics` listing page for curl_cffi. Use Chrome MCP `evaluate_script` on the topics page to extract new topic IDs/slugs (see scraping notes).
3. **Scrape individual topics** — Individual topic pages work fine with curl_cffi. Use `scraper/thread.py` + `scraper/render.py` directly with the known IDs (see scraping notes).
4. **Read** — filter out agendas/admin noise (~half the corpus). Substantive threads are anything that's *not*: `agenda-for-…`, `meeting-(agenda|minutes)-…`, `no-(twi-)?meeting-…`, `cannot-attend-…`, `respond-if-you-plan-to-attend-…`, single-sentence threads.
5. **Write** — `Write` tool directly to `data/twi/`. Cite every factual claim with the originating thread filename.
6. **Append to `log.md`**, then **commit** (separate commits for raw thread `.md` additions and wiki authoring).

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

- **Bot detection on listing pages**: groups.io added Spur MCL JavaScript bot detection to `/topics` listing pages in mid-2026. `curl_cffi` (even with `impersonate="chrome"`) gets a 2 KB challenge page instead of content, so `discover_all_topics` returns 0. **Individual topic pages are not affected** — curl_cffi fetches them fine.
- **Workaround — two-phase scrape**:
  1. **Topic discovery**: Use Chrome MCP to navigate to `https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topics` (already authenticated), then `evaluate_script` → `[...document.querySelectorAll('a[href*="/topic/"]')].map(a => ({href: a.href, text: a.textContent.trim()}))` to get topic IDs and slugs. Extract only IDs greater than the last known topic ID.
  2. **Individual scrape**: For each new topic, call `scraper/thread.py::parse_thread()` + `scraper/render.py::write_thread()` directly.
- **Cookie refresh**: Navigate to `https://lists.confidentialcomputing.io/login` (NOT `groups.io/login`) → redirects to Linux Foundation SSO at `sso.linuxfoundation.org` → sign in with `hangyin@phala.network` / stored password → "Proceed To List" → navigate to TWI SIG topics page → capture the `Cookie:` request header from a network request (`list_network_requests` + `get_network_request`) → update `GROUPSIO_COOKIE` in `.env`. Note: `document.cookie` only returns `cookieconsent_status`; the `groupsio` session cookie is httpOnly and only visible in network headers.
- **Cookie domain**: `lists.confidentialcomputing.io` (a groups.io custom-domain instance). Login via plain `groups.io` does NOT work — the account uses Linux Foundation SSO.
- `data/raw/` is the response cache (gitignored). `make clean-cache` wipes it. Only topic content pages are cached; topic listing pages are no longer cached (Spur challenge pages would poison the cache).

## Scraping notes (linux-coco)

- **Source**: public-inbox git mirror at `linux-coco/git/0.git`. Fetch with `git fetch` inside the bare repo.
- **Extraction**: `scraper/linux-coco/extract.py` queries `linux-coco/xap15/over.sqlite3` for message metadata (subject, from, blob hash, thread ID), then reads email bytes via `git cat-file blob <hash>`.
- `over.sqlite3` computes thread grouping (`tid`) automatically — no need to parse References headers.
- Date range: pass `SINCE` / `UNTIL` to `load_messages()` to extract a time window incrementally.

## Things to *not* do

- Don't batch-write wiki pages using an MCP loop. Use `Write` directly to the filesystem.
- Don't write wiki pages without footnote citations to source filenames.
- Don't commit `linux-coco/` (gitignored, 600MB public-inbox mirror).
