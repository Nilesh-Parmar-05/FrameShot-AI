"""Wikipedia REST API client for entity and landmark summaries.

Task 3.1 & 3.3 in ``tasks.md``.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from dataclasses import asdict, dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "FrameShot-AI/0.1.0 (https://github.com/frameshot/frameshot; companion@frameshot.ai)"
HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True, slots=True)
class WikipediaSummary:
    """Structured summary response from Wikipedia."""

    title: str
    extract: str
    description: str | None = None
    thumbnail_url: str | None = None
    page_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WikipediaSummary:
        return cls(
            title=data.get("title", ""),
            extract=data.get("extract", ""),
            description=data.get("description"),
            thumbnail_url=data.get("thumbnail_url"),
            page_url=data.get("page_url"),
        )


class WikipediaClient:
    """Client for Wikipedia's official REST API summary endpoint."""

    BASE_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        if hasattr(self._session, "headers") and hasattr(self._session.headers, "update"):
            self._session.headers.update({"User-Agent": USER_AGENT})

    def fetch_summary(self, title: str, timeout_s: float = 2.0) -> WikipediaSummary | None:
        """Fetch summary extract, thumbnail, and description for a given page title.

        Returns None gracefully on 404, network error, or timeout.
        """
        clean_title = title.strip()
        if not clean_title:
            return None

        encoded_title = urllib.parse.quote(clean_title.replace(" ", "_"))
        url = f"{self.BASE_URL}/{encoded_title}"

        try:
            response = self._session.get(url, timeout=timeout_s)
            if response.status_code == 404:
                logger.debug("Wikipedia entry not found for: %s", clean_title)
                return None
            response.raise_for_status()
            data = response.json()

            extract = data.get("extract", "")
            if not extract:
                return None

            page_title = data.get("titles", {}).get("display") or data.get("title", clean_title)
            clean_page_title = HTML_TAG_RE.sub("", str(page_title)).strip()
            description = data.get("description")
            thumb_url = data.get("thumbnail", {}).get("source")
            page_url = data.get("content_urls", {}).get("desktop", {}).get("page")

            return WikipediaSummary(
                title=clean_page_title,
                extract=extract,
                description=description,
                thumbnail_url=thumb_url,
                page_url=page_url,
            )
        except requests.RequestException as exc:
            logger.debug("Wikipedia fetch failed for '%s': %s", clean_title, exc)
            return None
        except Exception as exc:
            logger.warning("Unexpected error parsing Wikipedia response for '%s': %s", clean_title, exc)
            return None
