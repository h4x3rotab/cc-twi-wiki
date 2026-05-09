"""Entry point: extract threads from public-inbox mirror and write markdown."""

import datetime
import sys
from pathlib import Path

from .extract import load_messages, group_into_threads
from .render import write_threads, OUT_DIR

SINCE = datetime.datetime(2025, 5, 8, tzinfo=datetime.timezone.utc)


def main():
    print(f"Loading messages since {SINCE.date()} …")
    messages = load_messages(since=SINCE)
    print(f"Loaded {len(messages)} messages")

    threads = group_into_threads(messages)
    print(f"Grouped into {len(threads)} threads")

    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DIR
    written = write_threads(threads, out_dir)
    print(f"Wrote {len(written)} files to {out_dir}")


if __name__ == "__main__":
    main()
