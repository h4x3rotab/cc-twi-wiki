# Confidential Computing Wiki Hub

A browsable wiki of two confidential computing mailing list archives:

- **CCC TWI SIG** — `lists.confidentialcomputing.io` (groups.io), scraped with a logged-in cookie
- **linux-coco** — `linux-coco@lists.linux.dev` (lore.kernel.org), mirrored via public-inbox

Served as a single site using [repoview](https://www.npmjs.com/package/repoview).

## Quick start

```bash
npm install
npm start         # → http://localhost:3000
```

## Scraping

### TWI SIG (groups.io)

Groups.io blocks unauthenticated traffic with a 402. You need a logged-in cookie:

```bash
cp .env.example .env
$EDITOR .env      # paste GROUPSIO_COOKIE (from browser DevTools → Network → Cookie header)
make install      # create Python venv
make scrape-twi   # → data/twi/threads/<id>-<slug>.md
```

`data/raw/` is a raw-HTML cache (gitignored). Reruns skip already-fetched URLs. `make clean-cache` wipes it. If you see 402 errors, refresh the cookie.

### linux-coco (public-inbox)

```bash
# First-time: fetch the public-inbox mirror (~87MB git + ~500MB Xapian index)
git clone --mirror https://lore.kernel.org/linux-coco/0 linux-coco/git/0.git
public-inbox-init -V2 --ng dev.linux.lists.linux-coco \
  linux-coco ./linux-coco https://lore.kernel.org/linux-coco linux-coco@lists.linux.dev
public-inbox-index ./linux-coco

# Incremental update
cd linux-coco/git/0.git && git fetch origin && cd -
public-inbox-index ./linux-coco
make scrape-linux-coco   # → data/linux-coco/threads/YYYYMMDD-slug.md
```

## Layout

```
data/
├── index.md               ← root landing page
├── twi/                   ← TWI SIG wiki
│   ├── overview.md
│   ├── concepts/
│   ├── entities/
│   ├── timeline.md
│   └── threads/           ← raw scraped threads
└── linux-coco/            ← linux-coco wiki
    ├── overview.md
    ├── concepts/
    ├── entities/
    ├── timeline.md
    └── threads/           ← raw thread files (YYYYMMDD-slug.md)
```

See `CLAUDE.md` for the wiki authoring methodology and citation conventions.

## Deployment

Configured for [Nixpacks](https://nixpacks.com) (`nixpacks.toml`). Set `PORT` to override the default port (3000).
