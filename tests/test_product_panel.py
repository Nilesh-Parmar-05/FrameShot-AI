"""Unit tests for ProductMatch and ProductPanel."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from frameshot.vision_pipeline import Detection, ProductMatch, VisionPipeline


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app


def test_product_match_properties():
    prod = ProductMatch(
        name="Desktop PC Tower",
        category="Electronics",
        search_query="desktop pc tower computer workstation",
        description="Mid-tower computer workstation",
        icon="💻",
    )
    assert prod.name == "Desktop PC Tower"
    assert prod.category == "Electronics"
    assert "https://www.amazon.in/s?k=" in prod.amazon_url
    assert "desktop+pc+tower" in prod.amazon_url
    assert "desktop+pc+tower" in prod.google_shopping_url
    assert "desktop+pc+tower" in prod.web_url


def test_vision_pipeline_match_products():
    pipe = VisionPipeline()

    # Empty detections
    assert pipe.match_products(detections=[]) == []

    # Scene with person, tv (screen), chair
    detections = [
        Detection(label="person", category="person", confidence=0.9, bbox=(10, 10, 100, 200)),
        Detection(label="tv", category="electronics", confidence=0.85, bbox=(150, 50, 300, 250)),
        Detection(label="chair", category="furniture", confidence=0.75, bbox=(50, 150, 120, 300)),
    ]

    products = pipe.match_products(detections=detections)
    assert len(products) >= 4

    names = [p.name for p in products]
    categories = [p.category for p in products]

    # Check clothes
    assert any("Shirt" in name or "Polo" in name for name in names)
    assert "Clothing" in categories

    # Check CPU and Screen
    assert any("CPU" in name or "PC Tower" in name for name in names)
    assert any("Monitor" in name or "Screen" in name for name in names)
    assert "Electronics" in categories

    # Check Furniture
    assert any("Chair" in name for name in names)
    assert "Furniture" in categories


def test_product_panel_ui(qapp):
    from frameshot.ui.product_panel import ProductCard, ProductPanel

    panel = ProductPanel()

    prod = ProductMatch(
        name="White Polo Work Shirt",
        category="Clothing",
        search_query="white polo collared shirt",
        description="Office polo shirt",
        icon="👔",
    )

    card = ProductCard(prod)
    assert card is not None

    # Populate panel
    panel.update_content([prod])
    assert panel.cards_layout.count() >= 2  # card + stretch

    # Empty state
    panel.update_content([])
    assert panel.cards_layout.count() >= 2  # empty_frame + stretch


def test_search_google_lens_redirect(monkeypatch, tmp_path):
    from frameshot.ui.product_panel import search_google_lens

    opened_urls: list[str] = []
    monkeypatch.setattr("frameshot.ui.product_panel.open_browser_url", lambda url: opened_urls.append(url))

    # Create dummy crop file
    crop_file = tmp_path / "crop.jpg"
    crop_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

    class MockResponse:
        status_code = 200
        text = "https://files.catbox.moe/abc123xyz.jpg"

    monkeypatch.setattr("requests.post", lambda *a, **kw: MockResponse())

    search_google_lens(str(crop_file), "white polo shirt")
    assert len(opened_urls) == 1
    assert "uploadbyurl?url=" in opened_urls[0]
    assert "abc123xyz.jpg" in opened_urls[0]


def test_search_google_lens_fallback(monkeypatch):
    from frameshot.ui.product_panel import search_google_lens

    opened_urls: list[str] = []
    monkeypatch.setattr("frameshot.ui.product_panel.open_browser_url", lambda url: opened_urls.append(url))

    # None crop -> fallback to shopping search
    search_google_lens(None, "black office chair")
    assert len(opened_urls) == 1
    assert "tbm=shop" in opened_urls[0]
    assert "black+office+chair" in opened_urls[0]

