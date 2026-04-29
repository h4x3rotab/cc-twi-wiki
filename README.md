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
#    Two Python venvs because api/ and mcp/ have different deps.
cd llmwiki
python3 -m venv api/.venv && . api/.venv/bin/activate && \
  pip install -r api/requirements.txt && deactivate
python3 -m venv mcp/.venv && . mcp/.venv/bin/activate && \
  pip install -r mcp/requirements.txt && deactivate
( cd web && npm install )
cd ..
```

## Use

```bash
make scrape   # scrape archive → data/threads/<id>-<slug>.md
make build    # llmwiki init data/threads
make serve    # llmwiki serve data/threads → http://localhost:3000
              # ports collide? `make serve LLMWIKI_API_PORT=8001 LLMWIKI_WEB_PORT=3001`
              # Expose over tailnet/LAN (binds 0.0.0.0, builds for prod):
              #   make serve LLMWIKI_HOST=<tailnet-ip> LLMWIKI_PROD=1 \
              #              LLMWIKI_API_PORT=8001 LLMWIKI_WEB_PORT=3001
```

`data/raw/` is a raw-HTML cache (gitignored). Reruns of `make scrape` skip already-fetched URLs. `make clean-cache` wipes it.

If you start seeing 402 errors during `make scrape`, your cookie has expired — paste a fresh one into `.env` and rerun.

## Connect Claude (MCP)

Once threads are scraped and `llmwiki init` has indexed them, hand the workspace to Claude over MCP so Claude can author the wiki:

```bash
cd llmwiki
./llmwiki mcp-config ../data/threads
```

This prints a `mcpServers` snippet. For Claude Code, save it as `.mcp.json` at the repo root (or merge it into `~/.claude.json`):

```json
{
  "mcpServers": {
    "llmwiki-threads": {
      "command": "/abs/path/to/llmwiki/llmwiki",
      "args": ["mcp", "/abs/path/to/data/threads"]
    }
  }
}
```

Restart Claude Code so it picks up the new MCP server, then ask: *"Read the guide, then ingest my sources and start building the wiki."*

The MCP server uses `mcp/.venv` for its deps — running `make install` in this repo doesn't set that up, only the llmwiki step in **Setup** above does.

## Layout

See `docs/superpowers/specs/2026-04-29-twi-wiki-design.md` for the design.
