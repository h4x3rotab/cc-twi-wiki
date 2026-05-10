"""Render a Thread to a markdown file suitable as llmwiki input."""

from __future__ import annotations

import json
import re
from pathlib import Path

from markdownify import markdownify

from .thread import Thread


THREADS_DIR = Path("data/twi/threads")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 60) -> str:
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return s[:max_len].rstrip("-") or "untitled"


def _yaml_value(v) -> str:
    """Produce a YAML-safe scalar for our limited frontmatter shapes."""
    return json.dumps(v, ensure_ascii=False, default=str)


def _frontmatter(thread: Thread) -> str:
    msgs = thread.messages
    participants = sorted({m.sender_name for m in msgs if m.sender_name})
    first = msgs[0].timestamp_utc.date().isoformat() if msgs else ""
    last = msgs[-1].timestamp_utc.date().isoformat() if msgs else ""
    lines = [
        "---",
        f"topic_id: {thread.topic_id}",
        f"subject: {_yaml_value(thread.subject)}",
        f"participants: {_yaml_value(participants)}",
        f"first_post: {first}",
        f"last_post: {last}",
        f"message_count: {len(msgs)}",
        f"source: {thread.source_url}",
        "---",
        "",
    ]
    return "\n".join(lines)


def render_thread(thread: Thread) -> str:
    parts = [_frontmatter(thread), f"# {thread.subject}", ""]
    for i, m in enumerate(thread.messages, start=1):
        ts_iso = m.timestamp_utc.strftime("%Y-%m-%d %H:%M UTC")
        parts.append(f"## Message {i} (#{m.msg_num}) — {m.sender_name} — {ts_iso}")
        parts.append("")
        body_md = markdownify(m.body_html, heading_style="ATX", strip=["script", "style"]).strip()
        parts.append(body_md or "_(empty body)_")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def write_thread(thread: Thread, out_dir: Path = THREADS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(thread.subject)
    path = out_dir / f"{thread.topic_id}-{slug}.md"
    path.write_text(render_thread(thread), encoding="utf-8")
    return path
