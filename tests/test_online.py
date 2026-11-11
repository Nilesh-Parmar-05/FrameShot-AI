"""Unit tests for Phase 3 Online Enrichment (Wikipedia, Wiktionary, SQLite TTL Cache)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import requests

from frameshot.config import AppConfig
from frameshot.database import Database
from frameshot.online import (
    EnrichmentService,
    WikipediaClient,
    WikipediaSummary,
    WiktionaryClient,
)


def test_database_cache_crud(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)

    # Initial get on empty cache
    assert db.get_cache("wiki:eiffel") is None

    # Set cache with 1 day TTL
    data = {"title": "Eiffel Tower", "extract": "A wrought-iron lattice tower."}
    db.set_cache("wiki:eiffel", "wikipedia", json.dumps(data), ttl_seconds=86400)

    # Retrieve cached
    cached = db.get_cache("wiki:eiffel")
    assert cached is not None
    loaded = json.loads(cached)
    assert loaded["title"] == "Eiffel Tower"

    # Overwrite cache
    data["extract"] = "Updated extract."
    db.set_cache("wiki:eiffel", "wikipedia", json.dumps(data), ttl_seconds=86400)
    cached2 = db.get_cache("wiki:eiffel")
    assert cached2 is not None
    assert json.loads(cached2)["extract"] == "Updated extract."


def test_database_cache_expiry(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)

    # Insert an already-expired item with negative TTL
    db.set_cache("exp:key", "test", '{"msg": "expired"}', ttl_seconds=-10)

    # get_cache should return None because it's expired
    assert db.get_cache("exp:key") is None

    # purge_expired_cache should remove the row
    deleted = db.purge_expired_cache()
    assert deleted >= 1


def test_wikipedia_client_success():
    mock_session = MagicMock(spec=requests.Session)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "title": "Colosseum",
        "extract": "The Colosseum is an oval amphitheatre in the centre of Rome.",
        "description": "Ancient amphitheatre in Rome, Italy",
        "thumbnail": {"source": "https://example.com/colosseum.jpg"},
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Colosseum"}},
    }
    mock_session.get.return_value = mock_resp

    client = WikipediaClient(session=mock_session)
    summary = client.fetch_summary("Colosseum")

    assert summary is not None
    assert summary.title == "Colosseum"
    assert "amphitheatre" in summary.extract
    assert summary.thumbnail_url == "https://example.com/colosseum.jpg"
    assert summary.page_url == "https://en.wikipedia.org/wiki/Colosseum"


def test_wikipedia_client_404_and_errors():
    mock_session = MagicMock(spec=requests.Session)
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_session.get.return_value = mock_resp

    client = WikipediaClient(session=mock_session)
    assert client.fetch_summary("NonExistentItem12345") is None

    # Test network exception
    mock_session.get.side_effect = requests.RequestException("DNS lookup failed")
    assert client.fetch_summary("ErrorItem") is None

    # Test empty query
    assert client.fetch_summary("   ") is None


def test_wiktionary_client_success():
    mock_session = MagicMock(spec=requests.Session)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "en": [
            {
                "partOfSpeech": "Adjective",
                "definitions": [
                    {
                        "definition": "Having great beauty and <i>splendor</i>.",
                        "examples": ["The palace was resplendent."],
                    }
                ],
            }
        ]
    }
    mock_session.get.return_value = mock_resp

    client = WiktionaryClient(session=mock_session)
    details = client.fetch_details("resplendent")

    assert details is not None
    assert details.word == "resplendent"
    assert len(details.definitions) == 1
    d = details.definitions[0]
    assert d.part_of_speech == "adjective"
    assert d.definition == "Having great beauty and splendor."  # HTML stripped
    assert d.examples == ["The palace was resplendent."]


def test_wiktionary_client_errors():
    mock_session = MagicMock(spec=requests.Session)
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_session.get.return_value = mock_resp

    client = WiktionaryClient(session=mock_session)
    assert client.fetch_details("notarealwordxyz") is None

    mock_session.get.side_effect = requests.RequestException("Connection timed out")
    assert client.fetch_details("word") is None
    assert client.fetch_details("") is None


def test_enrichment_service_offline_safety(config: AppConfig, tmp_path):
    config.online.enabled = False  # Explicitly disabled
    db = Database(tmp_path / "enrich.db")
    mock_wiki = MagicMock(spec=WikipediaClient)
    mock_wiktionary = MagicMock(spec=WiktionaryClient)

    service = EnrichmentService(
        config=config,
        database=db,
        wiki_client=mock_wiki,
        wiktionary_client=mock_wiktionary,
    )

    # When offline, requests must NEVER hit the network clients
    assert service.enrich_word("ephemeral") is None
    assert service.enrich_entity("Eiffel Tower") is None
    mock_wiktionary.fetch_details.assert_not_called()
    mock_wiki.fetch_summary.assert_not_called()


def test_enrichment_service_caching_flow(config: AppConfig, tmp_path):
    config.online.enabled = True  # Enable online mode
    db = Database(tmp_path / "enrich.db")

    mock_wiki = MagicMock(spec=WikipediaClient)
    mock_wiki.fetch_summary.return_value = WikipediaSummary(
        title="Big Ben",
        extract="Big Ben is the nickname for the Great Bell of the Great Clock of Westminster.",
        page_url="https://en.wikipedia.org/wiki/Big_Ben",
    )

    service = EnrichmentService(
        config=config,
        database=db,
        wiki_client=mock_wiki,
    )

    # 1. First call: hits network client
    res1 = service.enrich_entity("Big Ben")
    assert res1 is not None
    assert res1.title == "Big Ben"
    assert mock_wiki.fetch_summary.call_count == 1

    # 2. Second call: should hit SQLite cache, NOT network client
    res2 = service.enrich_entity("Big Ben")
    assert res2 is not None
    assert res2.title == "Big Ben"
    assert mock_wiki.fetch_summary.call_count == 1  # Still 1! Cache hit!
