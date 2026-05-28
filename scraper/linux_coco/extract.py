"""
Extract threads from the public-inbox mirror.

Uses over.sqlite3 for metadata (thread grouping, timestamps, blob hashes)
and git cat-file to read the actual email bytes.
"""

import datetime
import email
import email.policy
import email.header
import email.utils
import re
import sqlite3
import subprocess
import zlib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
OVER_DB = ROOT / "linux-coco" / "xap15" / "over.sqlite3"
GIT_DIR = ROOT / "linux-coco" / "git" / "0.git"


@dataclass
class Message:
    num: int          # NNTP article number (unique, from DB)
    tid: int          # thread id (from DB)
    ts: int           # received timestamp (unix)
    message_id: str
    subject: str
    from_name: str
    from_addr: str
    date: datetime.datetime
    body: str
    blob_hash: str
    in_reply_to: str
    references: list[str] = field(default_factory=list)


@dataclass
class Thread:
    tid: int
    messages: list[Message] = field(default_factory=list)

    @property
    def subject(self) -> str:
        return _normalize_subject(self.messages[0].subject) if self.messages else ""

    @property
    def first_date(self) -> datetime.datetime:
        return min(m.date for m in self.messages)

    @property
    def last_date(self) -> datetime.datetime:
        return max(m.date for m in self.messages)

    @property
    def participants(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for m in self.messages:
            key = m.from_addr or m.from_name
            if key and key not in seen:
                seen.add(key)
                result.append(m.from_name or m.from_addr)
        return result


def _normalize_subject(s: str) -> str:
    s = s.strip()
    s = re.sub(r'^\[PATCH[^\]]*\]\s*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(re|fwd?|aw):\s*', '', s, flags=re.IGNORECASE)
    return s.strip()


def _decode_header(h: str) -> str:
    try:
        return str(email.header.make_header(email.header.decode_header(h or "")))
    except Exception:
        return h or ""


def _parse_ddd(raw: bytes) -> dict:
    """Parse the doc-data-deflated blob from over.sqlite3."""
    text = zlib.decompress(raw).decode("utf-8", errors="replace")
    lines = text.split("\n")
    return {
        "subject": lines[0] if len(lines) > 0 else "",
        "from":    lines[1] if len(lines) > 1 else "",
        "refs":    lines[2] if len(lines) > 2 else "",
        "blob":    lines[5] if len(lines) > 5 else "",
        "mid":     lines[6] if len(lines) > 6 else "",
    }


def _read_blob(blob_hash: str) -> bytes:
    result = subprocess.run(
        ["git", "--git-dir", str(GIT_DIR), "cat-file", "blob", blob_hash],
        capture_output=True, check=True,
    )
    return result.stdout


def _extract_body(msg: email.message.Message) -> str:
    """Extract plain-text body, stripping quoted lines and signatures."""
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    parts.append(part.get_content())
                except Exception:
                    payload = part.get_payload(decode=True)
                    if payload:
                        parts.append(payload.decode("utf-8", errors="replace"))
    else:
        try:
            parts.append(msg.get_content())
        except Exception:
            payload = msg.get_payload(decode=True)
            if payload:
                parts.append(payload.decode("utf-8", errors="replace"))
            else:
                parts.append(str(msg.get_payload() or ""))

    body = "\n".join(parts)

    # Strip long quoted blocks (lines starting with >)
    lines = body.splitlines()
    kept = []
    quote_run = 0
    for line in lines:
        if line.startswith(">"):
            quote_run += 1
            if quote_run <= 2:  # keep at most 2 quoted lines for context
                kept.append(line)
        else:
            quote_run = 0
            kept.append(line)

    # Strip signature
    text = "\n".join(kept)
    sig_match = re.search(r'\n-- \n', text)
    if sig_match:
        text = text[:sig_match.start()]

    return text.strip()


def load_messages(since: datetime.datetime, until: datetime.datetime | None = None) -> list[Message]:
    """Load all messages in [since, until) from the public-inbox DB."""
    since_ts = int(since.timestamp())
    until_ts = int(until.timestamp()) if until else int(datetime.datetime.now(datetime.timezone.utc).timestamp())

    db = sqlite3.connect(str(OVER_DB))
    rows = db.execute(
        "SELECT num, tid, ts, ds, ddd FROM over WHERE ts >= ? AND ts <= ? ORDER BY ts",
        (since_ts, until_ts),
    ).fetchall()
    db.close()

    messages: list[Message] = []
    for num, tid, ts, ds, ddd in rows:
        try:
            meta = _parse_ddd(ddd)
        except Exception:
            continue

        blob_hash = meta["blob"].strip()
        if not blob_hash:
            continue

        try:
            raw = _read_blob(blob_hash)
            msg = email.message_from_bytes(raw, policy=email.policy.compat32)
        except Exception:
            continue

        subject = _decode_header(msg.get("Subject", meta["subject"]))
        raw_from = msg.get("From", meta["from"])
        from_name, from_addr = email.utils.parseaddr(raw_from)
        from_name = _decode_header(from_name).strip()
        from_addr = from_addr.strip().lower()

        raw_date = msg.get("Date", "")
        try:
            date = email.utils.parsedate_to_datetime(raw_date)
            if date.tzinfo is None:
                date = date.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            date = datetime.datetime.fromtimestamp(ds or ts, tz=datetime.timezone.utc)

        in_reply_to = msg.get("In-Reply-To", "").strip().strip("<>")
        raw_refs = msg.get("References", meta["refs"])
        refs = [r.strip("<>") for r in raw_refs.split() if r.strip()]

        body = _extract_body(msg)
        mid = (msg.get("Message-ID") or meta["mid"]).strip().strip("<>")

        messages.append(Message(
            num=num,
            tid=tid,
            ts=ts,
            message_id=mid,
            subject=subject,
            from_name=from_name,
            from_addr=from_addr,
            date=date,
            body=body,
            blob_hash=blob_hash,
            in_reply_to=in_reply_to,
            references=refs,
        ))

    return messages


def group_into_threads(messages: list[Message]) -> list[Thread]:
    """Group messages by tid (public-inbox already computed thread grouping)."""
    thread_map: dict[int, Thread] = {}
    for msg in messages:
        if msg.tid not in thread_map:
            thread_map[msg.tid] = Thread(tid=msg.tid)
        thread_map[msg.tid].messages.append(msg)

    for t in thread_map.values():
        t.messages.sort(key=lambda m: m.date)

    return sorted(thread_map.values(), key=lambda t: t.first_date)
