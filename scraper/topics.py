"""Topic discovery: walk paginated /topics pages and collect topic URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from .fetch import GROUP_BASE, Fetcher


TOPIC_HREF = re.compile(
    r"^https://lists\.confidentialcomputing\.io/g/Trustworthy-Workload-Identity-SIG/topic/[^/]+/(\d+)$"
)


@dataclass(frozen=True)
class TopicRef:
    topic_id: int
    slug: str
    url: str


def parse_topic_links(html: str) -> list[TopicRef]:
    soup = BeautifulSoup(html, "lxml")
    seen: dict[int, TopicRef] = {}
    for a in soup.select("a[href*='/topic/']"):
        href = a.get("href", "")
        m = TOPIC_HREF.match(href)
        if not m:
            continue
        topic_id = int(m.group(1))
        # Slug is the segment between /topic/ and /<id>
        slug = href.split("/topic/", 1)[1].rsplit("/", 1)[0]
        if topic_id not in seen:
            seen[topic_id] = TopicRef(topic_id=topic_id, slug=slug, url=href)
    return list(seen.values())


def parse_max_page(html: str) -> int:
    """Return the largest page number found in pagination links (1 if single page)."""
    soup = BeautifulSoup(html, "lxml")
    pages = [1]
    for a in soup.select("a[href*='/topics?']"):
        href = a.get("href", "")
        m = re.search(r"[?&]page=(\d+)", href)
        if m:
            pages.append(int(m.group(1)))
    return max(pages)


def discover_all_topics(fetcher: Fetcher) -> list[TopicRef]:
    """Walk every /topics page and return the union of topic refs.

    Stops when a page yields no new topic IDs we haven't already seen — this
    handles groups.io's habit of advertising additional pages in the nav even
    after the actual last page.
    """
    refs: dict[int, TopicRef] = {}
    page = 1
    while True:
        url = f"{GROUP_BASE}/topics" if page == 1 else f"{GROUP_BASE}/topics?page={page}"
        html = fetcher.get(url)
        before = len(refs)
        for t in parse_topic_links(html):
            refs.setdefault(t.topic_id, t)
        if len(refs) == before:
            break
        page += 1
    return sorted(refs.values(), key=lambda t: t.topic_id)
