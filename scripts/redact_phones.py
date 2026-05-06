#!/usr/bin/env python3
"""Redact phone numbers in data/threads/**/*.md."""
import re
import sys
from pathlib import Path

PATTERNS = [
    # International with explicit +country, allowing spaces, dots, dashes, parens between digit groups.
    # Matches: +1(425)260-8728, +1 929 205 6099, +1 703-309-9446, +19292056099
    re.compile(r'\+\d{1,3}[\s.\-]?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}'),
    # US with parens: (XXX) XXX-XXXX
    re.compile(r'\(\d{3}\)\s*\d{3}[\s.\-]?\d{4}'),
    # US 3-3-4 with consistent separators (-, ., or space).
    # Word boundaries prevent mid-number matches.
    re.compile(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b'),
]

REPLACEMENT = "[redacted-phone]"

def redact(text: str) -> tuple[str, int]:
    count = 0
    for pat in PATTERNS:
        text, n = pat.subn(REPLACEMENT, text)
        count += n
    return text, count

def main(dry_run: bool):
    root = Path("data/threads")
    total = 0
    touched = 0
    for path in sorted(root.rglob("*.md")):
        original = path.read_text()
        new, n = redact(original)
        if n:
            print(f"{path}: {n} match(es)")
            total += n
            touched += 1
            if not dry_run:
                path.write_text(new)
    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"\n{mode}: {total} redactions across {touched} files")

if __name__ == "__main__":
    main(dry_run="--apply" not in sys.argv)
