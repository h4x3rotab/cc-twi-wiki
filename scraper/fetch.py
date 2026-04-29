"""HTTP fetcher for groups.io.

Uses curl_cffi with Chrome impersonation + a session cookie loaded from
$GROUPSIO_COOKIE to bypass the "Groups.io AI Crawler Policy" 402 page.
Caches each response on disk so reruns are free.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path

from curl_cffi import requests
from dotenv import load_dotenv


GROUP_BASE = "https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG"
RAW_DIR = Path("data/raw")
FAILURES_LOG = RAW_DIR / "failures.log"


class FetchError(RuntimeError):
    pass


def _cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode()).hexdigest()[:16]
    # Keep a hint of the URL in the filename for human grepping.
    tail = url.rsplit("/", 1)[-1].split("?", 1)[0][:40] or "root"
    return RAW_DIR / f"{tail}-{digest}.html"


class Fetcher:
    def __init__(self, delay_seconds: float = 0.5) -> None:
        load_dotenv()
        cookie = os.environ.get("GROUPSIO_COOKIE", "").strip()
        if not cookie:
            raise FetchError(
                "GROUPSIO_COOKIE is empty. Paste a logged-in groups.io cookie "
                "into .env (see README)."
            )
        # Strip quotes if user wrapped the value.
        if cookie.startswith('"') and cookie.endswith('"'):
            cookie = cookie[1:-1]
        self._session = requests.Session(
            impersonate="chrome",
            headers={
                "Cookie": cookie,
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        self._delay = delay_seconds
        RAW_DIR.mkdir(parents=True, exist_ok=True)

    def get(self, url: str, *, use_cache: bool = True) -> str:
        path = _cache_path(url)
        if use_cache and path.exists():
            return path.read_text(encoding="utf-8")
        time.sleep(self._delay)
        r = self._session.get(url, timeout=60)
        if r.status_code == 402:
            raise FetchError(
                f"402 from {url} — groups.io AI Crawler Policy. Refresh "
                f"GROUPSIO_COOKIE in .env from a logged-in browser session."
            )
        if r.status_code != 200:
            FAILURES_LOG.parent.mkdir(parents=True, exist_ok=True)
            with FAILURES_LOG.open("a", encoding="utf-8") as f:
                f.write(f"{r.status_code}\t{url}\n")
            raise FetchError(f"{r.status_code} from {url}")
        path.write_text(r.text, encoding="utf-8")
        return r.text


def main() -> None:
    """Smoke test: fetch the topics page and print its size."""
    f = Fetcher()
    html = f.get(f"{GROUP_BASE}/topics")
    print(f"OK len={len(html)}", file=sys.stderr)


if __name__ == "__main__":
    main()
