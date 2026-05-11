---
name: llmwiki
description: Build and maintain a persistent, structured wiki from any data source — mailing lists, papers, transcripts, Slack exports, or other noisy corpora. Synthesizes sources into interconnected markdown pages you own and can browse. Based on Karpathy's LLM Wiki pattern, hardened with real-world conventions.
---

# LLM Wiki

A skill for turning any collection of raw sources into a persistent, browsable knowledge base that compounds over time. You provide the sources; Claude writes and maintains all the wiki pages.

This is not RAG. Instead of re-deriving answers from raw documents on every query, Claude builds a **persistent wiki** — interconnected markdown pages that integrate, reconcile, and cross-reference knowledge. Every ingest makes the wiki richer. The synthesis is done once and kept current, not repeated.

---

## Three Layers

```
sources/          ← immutable raw input (never modified)
wiki/             ← Claude-authored markdown (the persistent artifact)
CLAUDE.md         ← schema: conventions, workflows, domain-specific rules
```

Claude owns the wiki layer entirely. You own the sources and the schema. You curate; Claude maintains.

---

## Step 0 — Bootstrap a new wiki

When starting from scratch, do this first:

1. **Assess the corpus.** Before writing a single page, read a representative sample of sources (at least 10–20%). Note: the domain vocabulary, the recurring entities and concepts, what fraction of sources are noise (see below), and what the most important threads or claims are.

2. **Design the schema.** Based on the assessment, decide:
   - Entity types (e.g. `people`, `orgs`, `projects`, `specs`, `papers`)
   - Concept groupings (e.g. `security`, `architecture`, `protocols`)
   - Whether a timeline is meaningful
   - What counts as signal vs. noise for this corpus

3. **Write `CLAUDE.md`** (or update it) with:
   - The layout conventions chosen above
   - Noise filter criteria specific to this corpus
   - Citation format and depth rules
   - Any domain-specific page templates

4. **Write `wiki/README.md`** — the root landing page. Describe the corpus, coverage dates, source count, and link to `overview.md`.

5. **Write `wiki/overview.md`** — high-level synthesis: what this corpus is about, key findings table, Mermaid structural diagram, wiki map linking to all sections.

---

## Noise Filtering (critical for real-world corpora)

Real corpora are noisy. Wikis built from noise are useless. **Always filter before writing.**

### What counts as noise (common patterns)

- **Meeting logistics**: agenda emails, "no meeting this week", attendance notices, "cannot attend", calendar invites
- **Pure admin**: subscription confirmations, list-management messages, bounces, automated notifications
- **Content-free acknowledgements**: "+1", "thanks", "agreed", single-sentence replies with no new claims
- **Duplicates / forwarded threads**: same content appearing multiple times
- **Off-topic**: tangential discussions that don't inform the wiki's subject matter

### Signal criteria

A source is worth ingesting if it contains **at least one** of:
- A technical claim, design decision, or architectural proposal
- A disagreement, trade-off discussion, or open question
- A named entity doing something notable (person, org, project, spec)
- A timeline event or milestone
- A contradiction of or update to something already in the wiki

### The filter pass

Before any synthesis pass, scan all sources and classify each as signal or noise. For mailing lists and discussion archives, expect ~30–50% noise. Do not write wiki content for noise sources. Record the noise ratio in `log.md`.

---

## Wiki Layout

```
wiki/
├── README.md               ← root landing page (auto-rendered by repoview/GitHub)
├── overview.md             ← high-level synthesis, key findings, Mermaid diagram, wiki map
├── timeline.md             ← chronological narrative with mermaid timeline block
├── log.md                  ← append-only record of ingests, lint passes, queries filed
├── concepts/
│   └── <topic>.md          ← one file per abstract idea or technology area
└── entities/
    ├── people/<name>.md
    ├── orgs/<name>.md
    ├── projects/<name>.md
    └── <other-type>/<name>.md
```

Raw sources live **outside** the wiki — in `sources/`, `threads/`, `data/`, or wherever they were placed. Never mix wiki pages with raw sources in the same directory.

---

## Page Conventions

Every wiki page must have:

**Frontmatter** (required):
```yaml
---
title: "Human-readable title"
description: "One sentence — used for index entries and link previews"
date: YYYY-MM-DD   # date of last significant update
tags: [tag1, tag2]  # at least 2
---
```

**At least one visual element** — a Mermaid diagram or a table. Prose-only pages are incomplete. Use a table for comparisons and status summaries; use Mermaid for relationships, flows, and timelines.

**Footnote citations** for every factual claim:
```markdown
TDX memory conversion runs during kexec shutdown.[^tdx-kexec]

[^tdx-kexec]: [20240508-x86-tdx-convert-shared.md](../sources/20240508-x86-tdx-convert-shared.md)
```

Citation link depth depends on page location relative to the sources directory:
- `wiki/*.md` → `../sources/FILE.md` (or whatever the sources dir is named)
- `wiki/concepts/*.md` → `../../sources/FILE.md`
- `wiki/entities/<type>/*.md` → `../../../sources/FILE.md`

**Cross-references** using relative markdown links to other wiki pages. Every entity and concept mentioned in a page should link to its page on first mention.

**No chat-style prose.** Wiki pages are permanent reference artifacts, not summaries of conversations. Write in a dense, encyclopedic register. "X was proposed by Y in [source]" not "Based on the threads, it seems like X might be related to Y."

---

## Ingest Operation

When adding new sources to an existing wiki:

1. **Filter noise** — classify new sources, skip noise, note ratio in log.
2. **Read signal sources in full** — understand before writing.
3. **One synthesis pass** — write all new and updated pages in a single pass using the `Write` tool directly to the filesystem. One pass keeps voice, cross-references, and terminology coherent.
   - New pages for new entities, concepts, or topics that lack coverage
   - Updated sections on existing pages where new sources add material
   - Updated `timeline.md` for any new events
   - Updated `overview.md` if the big picture changed
4. **Append to `log.md`**:
   ```
   ## [YYYY-MM-DD] ingest | <short description>
   Sources: N new (M noise filtered). Pages touched: X. New pages: Y.
   ```
5. **Commit** with a message that distinguishes raw source additions from wiki authoring (separate commits if both happened).

Do not use an MCP loop to iteratively write pages. Write all pages in one direct synthesis pass. Batch authoring produces more coherent cross-references and avoids inconsistency from incremental context drift.

---

## Query Operation

When answering questions against the wiki:

1. Read `wiki/README.md` and `wiki/overview.md` to orient.
2. Identify relevant concept and entity pages from the overview's wiki map.
3. Read those pages; follow cross-references as needed.
4. Synthesize an answer with citations to source filenames (not just wiki pages).
5. **File valuable answers back** — if the answer reveals a connection, comparison, or analysis that isn't already captured, write it as a new wiki page or section. Good queries should compound the wiki, not disappear into chat history.

---

## Lint Operation

Run periodically, or when the corpus has grown significantly:

Check for:
- **Contradictions** — pages making conflicting claims about the same thing
- **Stale claims** — assertions superseded by later sources
- **Orphan pages** — pages with no inbound links from other wiki pages
- **Missing pages** — entities or concepts mentioned across many pages but lacking their own page
- **Citation rot** — footnotes pointing to source files that were renamed or moved
- **Prose drift** — sections that have grown chat-like or lost their encyclopedic register

After a lint pass, append to `log.md`:
```
## [YYYY-MM-DD] lint
Issues found: N. Fixed: M. Deferred: K.
```

---

## Serving the Wiki

Any markdown-file server works. Recommended: [repoview](https://www.npmjs.com/package/repoview).

```bash
npm install repoview
npx repoview --repo wiki/ --host 0.0.0.0 --port 3000 --no-watch
```

repoview auto-renders `README.md` as a directory index (like GitHub). Structure `wiki/README.md` as the root landing page and `wiki/<subdir>/README.md` for sub-sections.

For larger wikis where the index file is no longer enough for navigation, add [qmd](https://github.com/tobi/qmd) — a local hybrid BM25/vector search engine for markdown with an MCP server interface.

---

## What NOT to Do

- **Don't write wiki pages without citations.** Uncited claims have no audit trail and become untrusted noise as the wiki grows.
- **Don't mix raw sources and wiki pages in the same directory.** It makes the wiki unbrowsable and confuses the citation depth calculation.
- **Don't write summaries that read like chat replies.** "Based on the threads, it seems like..." is wrong register for a wiki page.
- **Don't skip the noise filter.** Writing wiki pages from meeting logistics and +1 emails produces worthless content that's expensive to clean up later.
- **Don't ingest iteratively with an MCP loop.** Write all pages in one synthesis pass per ingest session.
- **Don't let answered queries disappear.** File valuable synthesis back into the wiki.

---

## Adapting to Your Corpus

This skill is intentionally generic. Before the first ingest, adjust these things in your `CLAUDE.md`:

| Variable | Mailing list | Research papers | Meeting transcripts |
|---|---|---|---|
| Noise filter | agendas, +1s, admin | rejected submissions, retracted | off-topic tangents, scheduling |
| Entity types | people, orgs, drafts | authors, institutions, datasets | people, action items, decisions |
| Citation format | thread filename | arxiv ID or DOI | transcript filename + timestamp |
| Timeline granularity | monthly | by publication date | by meeting date |
| Key visual | relationship graph | comparison table | decision flowchart |

The conventions above are defaults. Override them in `CLAUDE.md` for your domain. The schema file is what makes the LLM a disciplined maintainer across sessions rather than starting from scratch each time.
