#!/usr/bin/env python3
"""Rewrite footnote citations from bare filenames to relative markdown links.

markdown-it's `linkify` setting auto-detects `something.md` as a URL and
renders citations like `[^src]: 118990275-foo.md` as broken external links
to http://118990275-foo.md/. Wrapping the filename in a markdown link kills
the auto-linkifier and gives us a working click-through to the source thread.

Wiki pages live under data/threads/wiki/{,concepts/,entities/<sub>/}.
Source threads live at data/threads/<file>. We compute the per-page depth
to threads and rewrite each citation in place.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

THREADS_DIR = Path("data/threads")
WIKI_DIR = THREADS_DIR / "wiki"

# Match `[^name]: <filename>.md` at the start of a line, with the filename
# being a typical scraped thread name (digits-then-text). Avoid matching
# already-linked citations like `[^x]: [foo.md](bar)`.
CITATION = re.compile(
    r"^(\[\^[^\]]+\]:\s+)(\d{8,}-[A-Za-z0-9_.-]+\.md)\s*$",
    re.MULTILINE,
)


def relpath_to_thread(wiki_page: Path) -> str:
    """Return the relative-path prefix from a wiki page back to data/threads/."""
    # wiki_page is absolute or repo-relative; we want depth below data/threads/
    rel = wiki_page.resolve().relative_to(THREADS_DIR.resolve())
    # rel is like 'wiki/overview.md' or 'wiki/concepts/foo.md'
    depth = len(rel.parts) - 1  # number of dirs between page and threads/
    return "../" * depth


def fix_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    prefix = relpath_to_thread(path)

    def repl(m: re.Match) -> str:
        head, fname = m.group(1), m.group(2)
        return f"{head}[{fname}]({prefix}{fname})"

    new_text, n = CITATION.subn(repl, text)
    if n and new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return n


def main() -> int:
    if not WIKI_DIR.is_dir():
        print(f"error: {WIKI_DIR} not found", file=sys.stderr)
        return 1
    total_files = 0
    total_subs = 0
    for p in sorted(WIKI_DIR.rglob("*.md")):
        n = fix_file(p)
        if n:
            print(f"  {p}: {n} citations")
            total_files += 1
            total_subs += n
    print(f"\nfixed {total_subs} citations across {total_files} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
