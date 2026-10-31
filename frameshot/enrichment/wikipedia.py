"""Wikipedia summary client (FR-50, FR-51). Status: stub — task 3.1."""

from __future__ import annotations


class WikipediaClient:
    """Fetches ``/api/rest_v1/page/summary/<title>`` summaries."""

    def __init__(self, timeout_s: float = 5.0) -> None:
        self.timeout_s = timeout_s

    def summary(self, title: str, language: str = "en") -> str | None:
        raise NotImplementedError("tasks.md 3.1")
