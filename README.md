# TWI SIG Wiki

A local, browsable wiki of the Confidential Computing [Trustworthy Workload Identity SIG](https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG) mailing list. The scraper pulls the public groups.io archive (using a logged-in cookie since groups.io blocks unauthenticated/non-Chrome traffic with a "Groups.io AI Crawler Policy" 402 page), renders each thread as markdown, and feeds the corpus into a vendored copy of [llmwiki](https://github.com/lucasastorian/llmwiki).

## Setup

```bash
# 1. Get a cookie
#    Log into groups.io in Chrome as a member of the SIG.
#    Open DevTools → Network → reload the topics page → copy the
#    'Cookie' request header value. Paste it into .env:
cp .env.example .env
$EDITOR .env   # paste cookie into GROUPSIO_COOKIE

# 2. Install deps
make install

# 3. llmwiki has its own setup (Python + Node)
cd llmwiki
pip install -r api/requirements.txt
( cd web && npm install )
cd ..
```

## Use

```bash
make scrape   # scrape archive → data/threads/<id>-<slug>.md
make build    # llmwiki init data/threads
make serve    # llmwiki serve data/threads → http://localhost:3000
```

`data/raw/` is a raw-HTML cache (gitignored). Reruns of `make scrape` skip already-fetched URLs. `make clean-cache` wipes it.

If you start seeing 402 errors during `make scrape`, your cookie has expired — paste a fresh one into `.env` and rerun.

## Layout

See `docs/superpowers/specs/2026-04-29-twi-wiki-design.md` for the design.
