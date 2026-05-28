"""Render Thread objects to markdown files."""

import re
import unicodedata
from pathlib import Path

from .extract import Thread, Message

OUT_DIR = Path(__file__).parent.parent.parent / "data" / "linux-coco" / "threads"


def _slugify(text: str, maxlen: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode()
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:maxlen].rstrip('-')


def _format_date(dt) -> str:
    return dt.strftime("%Y-%m-%d")


def _strip_patch_prefix(subject: str) -> str:
    """Remove [PATCH N/M] style prefixes for display."""
    return re.sub(r'^\[PATCH[^\]]*\]\s*', '', subject, flags=re.IGNORECASE).strip()


def thread_filename(thread: Thread) -> str:
    """Return the markdown filename for a thread."""
    date = _format_date(thread.first_date).replace('-', '')
    slug = _slugify(_strip_patch_prefix(thread.subject))
    return f"{date}-{slug}.md"


def render_thread(thread: Thread) -> str:
    """Render a Thread to a markdown string."""
    subject = thread.subject
    date_str = _format_date(thread.first_date)
    last_str = _format_date(thread.last_date)
    participants = thread.participants

    # Frontmatter
    parts = [
        "---",
        f"title: {subject!r}",
        f"date: {date_str}",
        f"last_reply: {last_str}",
        f"message_count: {len(thread.messages)}",
        f"participants: {participants!r}",
        "---",
        "",
    ]

    # Messages
    for i, msg in enumerate(thread.messages):
        parts.append(f"## [{i+1}] {msg.from_name or msg.from_addr} — {_format_date(msg.date)}")
        if i > 0 and msg.subject and msg.subject.strip() != thread.messages[0].subject.strip():
            parts.append(f"*Subject: {msg.subject}*")
        parts.append("")
        body = msg.body.strip()
        if body:
            parts.append(body)
        parts.append("")
        parts.append("---")
        parts.append("")

    return "\n".join(parts)


def write_threads(threads: list[Thread], out_dir: Path = OUT_DIR) -> list[Path]:
    """Write all threads to markdown files and return the list of paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    seen_names: dict[str, int] = {}

    for thread in threads:
        name = thread_filename(thread)
        if name in seen_names:
            seen_names[name] += 1
            stem, _, ext = name.rpartition('.')
            name = f"{stem}-{seen_names[name]}.{ext}"
        else:
            seen_names[name] = 0

        path = out_dir / name
        path.write_text(render_thread(thread), encoding="utf-8")
        written.append(path)

    return written
