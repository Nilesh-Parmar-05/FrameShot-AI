"""Wiktionary REST API client for extended definitions, examples, and etymology.

Task 3.2 in ``tasks.md``.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from dataclasses import asdict, dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "FrameShot-AI/0.1.0 (https://github.com/frameshot/frameshot; companion@frameshot.ai)"
HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True, slots=True)
class WiktionaryDefinition:
    part_of_speech: str
    definition: str
    examples: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class WiktionaryDetails:
    word: str
    definitions: list[WiktionaryDefinition] = field(default_factory=list)
    etymology: str | None = None
    page_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "word": self.word,
            "definitions": [asdict(d) for d in self.definitions],
            "etymology": self.etymology,
            "page_url": self.page_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WiktionaryDetails:
        raw_defs = data.get("definitions", [])
        defs = [
            WiktionaryDefinition(
                part_of_speech=d.get("part_of_speech", ""),
                definition=d.get("definition", ""),
                examples=d.get("examples", []),
            )
            for d in raw_defs
        ]
        return cls(
            word=data.get("word", ""),
            definitions=defs,
            etymology=data.get("etymology"),
            page_url=data.get("page_url"),
        )


def _strip_html(text: str) -> str:
    """Strip basic HTML markup from Wiktionary API responses."""
    return HTML_TAG_RE.sub("", text).strip()


class WiktionaryClient:
    """Client for Wiktionary definitions and usage examples with dictionary fallback."""

    BASE_URL = "https://en.wiktionary.org/api/rest_v1/page/definition"
    FREE_DICT_URL = "https://api.dictionaryapi.dev/api/v2/entries/en"

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        if hasattr(self._session, "headers") and hasattr(self._session.headers, "update"):
            self._session.headers.update({"User-Agent": USER_AGENT})

    def _parse_wiktionary_json(
        self, clean_word: str, data: dict[str, Any], encoded: str
    ) -> WiktionaryDetails | None:
        en_sections = data.get("en", [])
        if not en_sections:
            return None

        definitions: list[WiktionaryDefinition] = []
        for sec in en_sections:
            pos = sec.get("partOfSpeech", "other").lower()
            for item in sec.get("definitions", []):
                raw_def = item.get("definition", "")
                clean_def = _strip_html(raw_def)
                if not clean_def:
                    continue

                examples: list[str] = []
                for ex in item.get("examples", []):
                    if isinstance(ex, str):
                        examples.append(_strip_html(ex))
                    elif isinstance(ex, dict) and "text" in ex:
                        examples.append(_strip_html(str(ex["text"])))

                definitions.append(
                    WiktionaryDefinition(
                        part_of_speech=pos,
                        definition=clean_def,
                        examples=examples[:3],
                    )
                )

        if not definitions:
            return None

        page_url = f"https://en.wiktionary.org/wiki/{encoded}"
        return WiktionaryDetails(
            word=clean_word,
            definitions=definitions[:5],
            page_url=page_url,
        )

    def _parse_free_dict_json(
        self, clean_word: str, data: list[dict[str, Any]], encoded: str
    ) -> WiktionaryDetails | None:
        definitions: list[WiktionaryDefinition] = []
        for entry in data:
            for m in entry.get("meanings", []):
                pos = m.get("partOfSpeech", "").lower()
                for d in m.get("definitions", []):
                    raw_def = d.get("definition", "")
                    clean_def = _strip_html(raw_def)
                    if not clean_def:
                        continue
                    examples: list[str] = []
                    if d.get("example"):
                        examples.append(_strip_html(str(d["example"])))
                    definitions.append(
                        WiktionaryDefinition(
                            part_of_speech=pos,
                            definition=clean_def,
                            examples=examples[:3],
                        )
                    )

        if not definitions:
            return None

        page_url = f"https://en.wiktionary.org/wiki/{encoded}"
        return WiktionaryDetails(
            word=clean_word,
            definitions=definitions[:5],
            page_url=page_url,
        )

    def fetch_details(self, word: str, timeout_s: float = 2.0) -> WiktionaryDetails | None:
        """Fetch definitions, parts of speech, and examples for an English word.

        Returns None on 404, network failure, or timeout.
        """
        clean_word = word.strip().lower()
        if not clean_word:
            return None

        encoded = urllib.parse.quote(clean_word)

        # 1. Try Wiktionary REST endpoint
        try:
            url = f"{self.BASE_URL}/{encoded}"
            response = self._session.get(url, timeout=timeout_s)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and "en" in data:
                    details = self._parse_wiktionary_json(clean_word, data, encoded)
                    if details:
                        return details
                elif isinstance(data, list):
                    details = self._parse_free_dict_json(clean_word, data, encoded)
                    if details:
                        return details
        except requests.RequestException as exc:
            logger.debug("Wiktionary fetch failed for '%s': %s", clean_word, exc)
        except Exception as exc:
            logger.warning("Unexpected error in Wiktionary response for '%s': %s", clean_word, exc)

        # 2. Try Free Dictionary API as fast fallback
        try:
            dict_url = f"{self.FREE_DICT_URL}/{encoded}"
            response = self._session.get(dict_url, timeout=timeout_s)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    details = self._parse_free_dict_json(clean_word, data, encoded)
                    if details:
                        return details
        except Exception as exc:
            logger.debug("Dictionary API fallback failed for '%s': %s", clean_word, exc)

        # 3. If word is plural, retry singular form (e.g. 'weekends' -> 'weekend')
        if clean_word.endswith("s") and len(clean_word) > 3:
            singular = clean_word[:-1]
            try:
                dict_url = f"{self.FREE_DICT_URL}/{urllib.parse.quote(singular)}"
                response = self._session.get(dict_url, timeout=timeout_s)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        details = self._parse_free_dict_json(clean_word, data, encoded)
                        if details:
                            return details
            except Exception:
                pass

        return None
