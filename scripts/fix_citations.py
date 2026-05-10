#!/usr/bin/env python3
"""Rewrite footnote citations from bare filenames to relative markdown links.

markdown-it's `linkify` setting auto-detects `something.md` as a URL and
renders citations like `[^src]: 20240508-foo.md` as broken external links.
Wrapping the filename in a markdown link fixes this.

Wiki pages live directly under data/<list>/{,concepts/,entities/<sub>/}.
Thread files live in data/<list>/threads/. Citation prefix depends on the
page's depth below its list root:
  overview.md, timeline.md, ...  → threads/<file>.md
  concepts/foo.md                → ../threads/<file>.md
  entities/patches/foo.md        → ../../threads/<file>.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LIST_ROOTS = [Path("data/twi"), Path("data/linux-coco")]

# Match bare `[^name]: <filename>.md` citations (not already-linked ones).
CITATION = re.compile(
    r"^(\[\^[^\]]+\]:\s+)(\d{6,}-[A-Za-z0-9_.-]+\.md)\s*$",
    re.MULTILINE,
)


def thread_prefix(wiki_page: Path, list_root: Path) -> str:
    """Relative path prefix from wiki_page to the list's threads/ directory."""
    rel = wiki_page.resolve().relative_to(list_root.resolve())
    depth = len(rel.parts) - 1  # number of directories between page and list root
    return "../" * depth + "threads/"


def fix_file(path: Path, list_root: Path) -> int:
    text = path.read_text(encoding="utf-8")
    prefix = thread_prefix(path, list_root)

    def repl(m: re.Match) -> str:
        head, fname = m.group(1), m.group(2)
        return f"{head}[{fname}]({prefix}{fname})"

    new_text, n = CITATION.subn(repl, text)
    if n and new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return n


def main() -> int:
    total_files = 0
    total_subs = 0
    for list_root in LIST_ROOTS:
        if not list_root.is_dir():
            continue
        for p in sorted(list_root.rglob("*.md")):
            if "threads" in p.parts:  # skip raw thread files themselves
                continue
            n = fix_file(p, list_root)
            if n:
                print(f"  {p}: {n} citations")
                total_files += 1
                total_subs += n
    print(f"\nfixed {total_subs} citations across {total_files} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
