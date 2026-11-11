"""Enrichment coordinator: checks opt-in status, consults SQLite TTL cache, and queries APIs.

Tasks 3.4 - 3.8 in ``tasks.md``.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frameshot.config import AppConfig
    from frameshot.database import Database

from frameshot.online.wikipedia_client import WikipediaClient, WikipediaSummary
from frameshot.online.wiktionary_client import WiktionaryClient, WiktionaryDetails

logger = logging.getLogger(__name__)


class EnrichmentService:
    """Coordinates online lookups with local caching and offline safety."""

    def __init__(
        self,
        config: AppConfig,
        database: Database | None = None,
        wiki_client: WikipediaClient | None = None,
        wiktionary_client: WiktionaryClient | None = None,
    ) -> None:
        self.config = config
        self.database = database
        self.wiki_client = wiki_client or WikipediaClient()
        self.wiktionary_client = wiktionary_client or WiktionaryClient()

    @property
    def is_enabled(self) -> bool:
        """Return True only if online enrichment is explicitly opted in."""
        return bool(self.config.online.enabled)

    def set_enabled(self, enabled: bool) -> None:
        """Dynamically toggle online mode (e.g. from UI or tray icon)."""
        self.config.online.enabled = enabled
        logger.info("Online enrichment %s", "enabled" if enabled else "disabled")

    # ------------------------------------------------------------ Word Enrichment

    def enrich_word(self, word: str) -> WiktionaryDetails | None:
        """Retrieve extended dictionary definitions and examples."""
        clean_word = word.strip().lower()
        if not clean_word:
            return None

        cache_key = f"wiktionary:{clean_word}"
        ttl_seconds = max(1, self.config.online.cache_ttl_days) * 86400

        # 1. Consult local database cache first (works even if offline!)
        if self.database is not None:
            try:
                cached_json = self.database.get_cache(cache_key)
                if cached_json:
                    data = json.loads(cached_json)
                    return WiktionaryDetails.from_dict(data)
            except Exception as exc:
                logger.debug("Cache read failed for '%s': %s", cache_key, exc)

        # 2. If online mode is disabled or service disabled, stop here without touching network
        if not self.is_enabled or not self.config.online.services.wiktionary:
            return None

        # 3. Live fetch from Wiktionary API
        details = self.wiktionary_client.fetch_details(clean_word)
        if details is not None and self.database is not None:
            try:
                self.database.set_cache(
                    key=cache_key,
                    source="wiktionary",
                    response_json=json.dumps(details.to_dict()),
                    ttl_seconds=ttl_seconds,
                )
            except Exception as exc:
                logger.debug("Cache write failed for '%s': %s", cache_key, exc)

        return details

    # ------------------------------------------------------------ Entity / Landmark Enrichment

    def enrich_entity(self, title: str) -> WikipediaSummary | None:
        """Retrieve encyclopedia summary and thumbnail for a landmark or entity."""
        clean_title = title.strip()
        if not clean_title:
            return None

        cache_key = f"wikipedia:{clean_title.lower()}"
        ttl_seconds = max(1, self.config.online.cache_ttl_days) * 86400

        # 1. Consult local database cache first
        if self.database is not None:
            try:
                cached_json = self.database.get_cache(cache_key)
                if cached_json:
                    data = json.loads(cached_json)
                    return WikipediaSummary.from_dict(data)
            except Exception as exc:
                logger.debug("Cache read failed for '%s': %s", cache_key, exc)

        # 2. Check online opt-in
        if not self.is_enabled or not self.config.online.services.wikipedia:
            return None

        # 3. Live fetch from Wikipedia REST API
        summary = self.wiki_client.fetch_summary(clean_title)
        if summary is not None and self.database is not None:
            try:
                self.database.set_cache(
                    key=cache_key,
                    source="wikipedia",
                    response_json=json.dumps(summary.to_dict()),
                    ttl_seconds=ttl_seconds,
                )
            except Exception as exc:
                logger.debug("Cache write failed for '%s': %s", cache_key, exc)

        return summary
