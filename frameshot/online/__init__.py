"""Online enrichment package (Wikipedia, Wiktionary, TTL cache)."""

from frameshot.online.enrichment_service import EnrichmentService
from frameshot.online.wikipedia_client import WikipediaClient, WikipediaSummary
from frameshot.online.wiktionary_client import (
    WiktionaryClient,
    WiktionaryDefinition,
    WiktionaryDetails,
)

__all__ = [
    "EnrichmentService",
    "WikipediaClient",
    "WikipediaSummary",
    "WiktionaryClient",
    "WiktionaryDefinition",
    "WiktionaryDetails",
]

