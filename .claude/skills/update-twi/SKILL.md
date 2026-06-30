---
name: update-twi
description: Sync the CCC TWI SIG mailing list archive and update the wiki. Handles the Spur MCL bot detection workaround, Linux Foundation SSO cookie refresh, and the full write → commit → push → Telegram flow.
---

# Update TWI SIG Wiki

Full procedure for syncing the TWI SIG mailing list and updating the wiki. Run when the user says "update TWI", "sync TWI", or similar.

## Quick summary

The TWI SIG mailing list lives at `lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG`. Bot detection on listing pages requires Chrome MCP for topic discovery; individual topic pages scrape fine with curl_cffi.

---

## Step 1 — Check what's new

Check the last sync date from `data/twi/log.md` and the highest topic ID in `data/twi/threads/`:

```bash
tail -5 data/twi/log.md
ls data/twi/threads/ | sort | tail -3
```

The filename prefix is the topic ID. Note the highest existing ID.

---

## Step 2 — Cookie health check

Try a quick scrape to see if the cookie is still valid:

```bash
make scrape-twi 2>&1 | head -5
```

- `found N topics` where N > 0: cache hit, move to Step 3 (but this is the old cache — still do Step 3 for new topics)
- `found 0 topics`: Spur bot detection is blocking listing pages. **This is normal** — go to Step 3 regardless, then check if Step 4 works.

Actually: skip `make scrape-twi` entirely. The listing-page bot detection means it will either use stale cached pages or return 0. Use Chrome MCP directly (Step 3).

---

## Step 3 — Discover new topics via Chrome MCP

### 3a. Check / refresh cookie

Navigate to the TWI SIG topics page. If already logged in (cookie valid), you'll land on the topics list. If not, you'll hit LF SSO.

```
navigate_page → https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topics
```

**If redirected to LF SSO** (`sso.linuxfoundation.org`):
1. Fill email: `hangyin@phala.network`
2. Fill password: (stored credential)
3. Click SIGN IN → "Proceed To List"
4. Navigate to TWI SIG topics page again

**Extract the fresh cookie** from a network request:
```
list_network_requests → get_network_request(reqid=N)
```
Copy the `Cookie:` request header value → update `GROUPSIO_COOKIE` in `.env`.

Note: `document.cookie` only returns `cookieconsent_status` (httpOnly cookies are invisible to JS).

### 3b. Extract topic IDs

```javascript
// evaluate_script on the topics page:
() => {
  const links = [...document.querySelectorAll('a[href*="/topic/"]')];
  return links.map(a => {
    const m = a.href.match(/\/topic\/([^/]+)\/(\d+)/);
    return m ? { id: parseInt(m[2]), slug: m[1], text: a.textContent.trim().substring(0, 80) } : null;
  }).filter(Boolean);
}
```

Filter to IDs greater than the last known topic ID. If there are more than 20 new topics (page 2+), navigate to subsequent pages and repeat.

---

## Step 4 — Scrape individual topics

```python
import os
os.environ['GROUPSIO_COOKIE'] = open('.env').read().split('GROUPSIO_COOKIE=')[1].strip().strip('"')

from scraper.fetch import Fetcher, GROUP_BASE
from scraper.thread import parse_thread
from scraper.render import write_thread

fetcher = Fetcher()

new_topics = [
    (119273859, "impossibility_of_rats_unaware"),
    # ... more (id, slug) tuples from Step 3b
]

for tid, slug in new_topics:
    url = f"{GROUP_BASE}/topic/{slug}/{tid}"
    html = fetcher.get(url)
    thread = parse_thread(tid, url, html)
    path = write_thread(thread)
    print(f"{tid} {len(thread.messages)}msg -> {path.name}")
```

Individual topic pages bypass the Spur MCL detection — curl_cffi works fine for them.

---

## Step 5 — Filter and read signal threads

**Noise** (skip these, do not update wiki):
- `agenda-for-…` (weekly meeting agendas — unless body has substantial new content)
- `meeting-(agenda|minutes)-…`
- `no-(twi-)?meeting-…` / `no-meeting-this-week-…`
- `cannot-attend-…` / `respond-if-you-plan-to-attend-…`
- Single-message threads with only logistics content
- Attendance confirmations / cancellations

**Signal** (include in wiki):
- Technical proposals, design decisions, architectural changes
- New draft documents or major draft revisions
- Cross-SIG discussions (Attestation SIG, WIMSE, RATS WG)
- Named entities doing something notable
- Contradictions or updates to previously captured claims
- Agenda messages that contain substantial substantive content (cite the agenda thread but extract the content)

---

## Step 6 — Update wiki pages

Pages most likely to need updating:

| New signal type | Wiki page(s) to update |
|---|---|
| New IETF draft / major revision | `entities/drafts/<draft>.md`, `timeline.md` |
| New formal paper or analysis | relevant `concepts/<topic>.md` |
| Design decision / architecture change | relevant `concepts/<topic>.md` |
| New person or org appears | `entities/people/<name>.md` or `entities/orgs/<name>.md` |
| Milestone event | `timeline.md` |
| All updates | `overview.md` (corpus count, date range), `log.md` |

Update corpus stats in `overview.md`:
- Thread count = `ls data/twi/threads/ | wc -l`
- Message count = rough sum from thread frontmatter
- Date range through = date of last thread

---

## Step 7 — Commit, push, and notify

```bash
# Commit 1: raw thread files
git add data/twi/threads/
git commit -m "Scrape TWI SIG through YYYY-MM-DD\n\nN new topics (date range). Bot detection workaround: individual pages.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

# Commit 2: wiki updates
git add data/twi/
git commit -m "Update TWI SIG wiki through YYYY-MM-DD\n\n<brief summary of what changed>\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

git push origin main
```

**Telegram announcement** — use the `tg-notify` skill. Format:

```
🔐 *CCC TWI SIG Wiki — <Month Year>*

<N> threads / ~<M> messages, Mar 2025 — <date>\.

*What's new:*

📄 *<Item 1>* — <1-sentence description>\. [→ <Page>](<url>)

🗺 *<Item 2>* — <1-sentence description>\. [→ <Page>](<url>)

[Browse the full wiki →](https://fqlqvbyr4fa5okgdw3vcx381.faraday.cloud)
```

Wiki page URL pattern: `https://fqlqvbyr4fa5okgdw3vcx381.faraday.cloud/blob/twi/<path>.md`
(The `/blob/` segment is required — links without it return 404.)

---

## Known issues

- **`make scrape-twi` is partially broken**: The Makefile target still works for cached content and individual page fetches, but `discover_all_topics()` returns 0 new topics because Spur MCL blocks listing pages. Use Chrome MCP for discovery (Step 3) and direct Python scraping for content (Step 4).
- **Cookie domain**: Must use `lists.confidentialcomputing.io` login, NOT `groups.io/login`. The account uses Linux Foundation SSO (not a direct groups.io password).
- **Pagination**: The topics page shows 20 topics per page. If there are many new topics, navigate to page 2+ in the browser and repeat Step 3b for each page.
