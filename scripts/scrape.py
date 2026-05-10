#!/usr/bin/env python3
"""Scrape the TWI SIG archive into data/twi/threads/<id>-<slug>.md."""

from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable when run as a script.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.fetch import FetchError, Fetcher  # noqa: E402
from scraper.render import write_thread  # noqa: E402
from scraper.thread import parse_thread  # noqa: E402
from scraper.topics import discover_all_topics  # noqa: E402


def main() -> int:
    fetcher = Fetcher()

    print("Discovering topics...", flush=True)
    refs = discover_all_topics(fetcher)
    print(f"  found {len(refs)} topics", flush=True)

    failures: list[tuple[int, str]] = []
    for i, ref in enumerate(refs, start=1):
        try:
            html = fetcher.get(ref.url)
            thread = parse_thread(ref.topic_id, ref.url, html)
            if not thread.messages:
                failures.append((ref.topic_id, "no messages parsed"))
                print(f"  [{i}/{len(refs)}] {ref.topic_id} EMPTY ({ref.slug})", flush=True)
                continue
            path = write_thread(thread)
            print(
                f"  [{i}/{len(refs)}] {ref.topic_id} {len(thread.messages):>2} msg "
                f"-> {path.name}",
                flush=True,
            )
        except FetchError as e:
            failures.append((ref.topic_id, str(e)))
            print(f"  [{i}/{len(refs)}] {ref.topic_id} FAILED: {e}", flush=True)
        except Exception as e:  # noqa: BLE001
            failures.append((ref.topic_id, repr(e)))
            print(f"  [{i}/{len(refs)}] {ref.topic_id} PARSE ERROR: {e!r}", flush=True)

    if failures:
        print(f"\n{len(failures)} failures:", flush=True)
        for tid, msg in failures:
            print(f"  topic {tid}: {msg}", flush=True)
        return 1
    print("\nAll topics scraped successfully.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
