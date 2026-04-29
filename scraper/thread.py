"""Parse a /topic/ page into structured Thread + Message records.

Groups.io renders the entire thread inline on the topic page (each message
is a `div.expanded-message`), so we only need one fetch per thread.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from bs4 import BeautifulSoup, Tag


@dataclass(frozen=True)
class Message:
    msg_num: int            # groups.io message number, e.g. 161
    sender_name: str
    timestamp_utc: datetime  # UTC datetime parsed from inline DisplayShortTime() script
    body_html: str          # contents of div.user-content, as raw HTML


@dataclass(frozen=True)
class Thread:
    topic_id: int
    subject: str
    source_url: str
    messages: list[Message] = field(default_factory=list)


_TS_RE = re.compile(r"DisplayShortTime\((\d+)")
_MSG_ID_RE = re.compile(r"^msg(\d+)$")


def _extract_subject(soup: BeautifulSoup) -> str:
    title = soup.find("title")
    if not title:
        return ""
    text = title.get_text(strip=True)
    # Format: "Trustworthy-Workload-Identity-SIG@... | <subject>"
    if "|" in text:
        return text.split("|", 1)[1].strip()
    return text


def _extract_msg_num(block: Tag) -> int | None:
    anchor = block.find("a", id=_MSG_ID_RE)
    if not anchor:
        return None
    m = _MSG_ID_RE.match(anchor.get("id", ""))
    return int(m.group(1)) if m else None


def _extract_sender(block: Tag) -> str:
    name_span = block.select_one(".user-chip-name")
    if name_span:
        return name_span.get_text(strip=True)
    chip = block.select_one(".user-chip-inner") or block.select_one(".user-chip")
    return chip.get_text(strip=True) if chip else ""


def _extract_timestamp_utc(block: Tag) -> datetime | None:
    """Pull the unix-nanosecond timestamp from the inline DisplayShortTime() script."""
    for script in block.find_all("script"):
        text = script.string or ""
        m = _TS_RE.search(text)
        if m:
            nanos = int(m.group(1))
            return datetime.fromtimestamp(nanos / 1_000_000_000, tz=timezone.utc)
    return None


def _extract_body_html(block: Tag) -> str:
    body = block.select_one("div.user-content")
    if not body:
        return ""
    # Decompose toggle-quoted-message UI elements that aren't part of the message text
    for el in body.select(".toggle-quoted, .quoted-message-toggle, button, .gio-toggle-quoted"):
        el.decompose()
    return body.decode_contents()


def parse_thread(topic_id: int, source_url: str, html: str) -> Thread:
    soup = BeautifulSoup(html, "lxml")
    subject = _extract_subject(soup)
    messages: list[Message] = []
    for block in soup.select("div.expanded-message"):
        msg_num = _extract_msg_num(block)
        if msg_num is None:
            continue
        ts = _extract_timestamp_utc(block)
        if ts is None:
            continue
        messages.append(
            Message(
                msg_num=msg_num,
                sender_name=_extract_sender(block),
                timestamp_utc=ts,
                body_html=_extract_body_html(block),
            )
        )
    messages.sort(key=lambda m: m.timestamp_utc)
    return Thread(topic_id=topic_id, subject=subject, source_url=source_url, messages=messages)
