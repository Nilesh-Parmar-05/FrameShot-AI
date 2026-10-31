"""Wiktionary lookup for extended definitions (FR-50). Status: stub — task 3.2."""

from __future__ import annotations


class WiktionaryClient:
    """Queries the MediaWiki API for a word's Wiktionary entry."""

    def __init__(self, timeout_s: float = 5.0) -> None:
        self.timeout_s = timeout_s

    def definitions(self, word: str, language: str = "en") -> list[str]:
        raise NotImplementedError("tasks.md 3.2")
