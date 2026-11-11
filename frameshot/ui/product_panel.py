"""Product Panel: Displays recognizable products, clothing, and gear with shopping links.

FR-33, FR-34, FR-52 in ``PRD.md``.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import urllib.parse
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from frameshot.vision_pipeline import Detection, ProductMatch

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QGuiApplication, QImage, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from frameshot.ui.theme import CATEGORY_COLORS, COLOR_CHIPS, Theme

logger = logging.getLogger(__name__)


def open_browser_url(url: str) -> None:
    """Open URL in user's default web browser."""
    try:
        q_url = QUrl(url)
        if not QDesktopServices.openUrl(q_url):
            webbrowser.open(url)
    except Exception as exc:
        logger.warning("Could not open product URL %s: %s", url, exc)
        with contextlib.suppress(Exception):
            webbrowser.open(url)


def upload_crop_to_public_host(crop_path: str) -> str | None:
    """Upload crop to an anonymous temporary host so Google Lens can fetch and render it."""
    # 1. Catbox.moe
    try:
        with Path(crop_path).open("rb") as f:
            resp = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": ("crop.jpg", f, "image/jpeg")},
                timeout=7.0,
            )
            if resp.status_code == 200 and resp.text.strip().startswith("http"):
                return resp.text.strip()
    except Exception as exc:
        logger.debug("Catbox upload failed: %s", exc)

    # 2. Tmpfiles.org fallback
    try:
        with Path(crop_path).open("rb") as f:
            resp = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": ("crop.jpg", f, "image/jpeg")},
                timeout=7.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_url = data.get("data", {}).get("url", "")
                if isinstance(raw_url, str) and raw_url:
                    return str(raw_url.replace("tmpfiles.org/", "tmpfiles.org/dl/"))
    except Exception as exc:
        logger.debug("Tmpfiles upload failed: %s", exc)

    return None


def search_google_lens(crop_path: str | None, fallback_query: str) -> None:
    """Perform direct Google Lens visual search by hosting the crop and querying uploadbyurl."""
    if crop_path and (crop_p := Path(crop_path)).is_file():
        image_url = upload_crop_to_public_host(str(crop_p))
        if image_url:
            encoded_url = urllib.parse.quote(image_url, safe="")
            lens_url = f"https://lens.google.com/uploadbyurl?url={encoded_url}"
            open_browser_url(lens_url)
            return

    # Fallback to direct Google Shopping search
    encoded = urllib.parse.quote_plus(fallback_query)
    open_browser_url(f"https://www.google.com/search?tbm=shop&q={encoded}")


class ProductCard(QFrame):
    """An individual styled card for a detected scene product or clothing item."""

    lens_ready = pyqtSignal()

    def __init__(self, product: ProductMatch, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.product = product
        self.lens_ready.connect(self._on_lens_ready)
        self.setObjectName("productCard")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        main_h_layout = QHBoxLayout(self)
        main_h_layout.setContentsMargins(12, 10, 12, 10)
        main_h_layout.setSpacing(10)

        # Left Thumbnail: anchored top-left
        if product.crop_path and Path(product.crop_path).is_file():
            pix = QPixmap(product.crop_path)
            if not pix.isNull():
                thumb_label = QLabel()
                thumb_label.setFixedSize(50, 50)
                scaled = pix.scaled(
                    50,
                    50,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                thumb_label.setPixmap(scaled)
                thumb_label.setStyleSheet(
                    f"border-radius: {Theme.RADIUS_SM}; "
                    f"border: 1px solid {Theme.BORDER_SUBTLE};"
                )
                thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                thumb_label.setToolTip("Scene visual crop used for Google Lens matching")
                main_h_layout.addWidget(thumb_label, 0, Qt.AlignmentFlag.AlignTop)

        # Right / Main content column
        content_v_layout = QVBoxLayout()
        content_v_layout.setContentsMargins(0, 0, 0, 0)
        content_v_layout.setSpacing(5)

        # 1. Top Metadata Row: Badges (Category + Color Chip)
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(6)

        cat_lower = product.category.lower()
        fg_col, bg_col, border_col = CATEGORY_COLORS.get(cat_lower, CATEGORY_COLORS["object"])
        cat_badge = QLabel(product.category.upper())
        cat_badge.setObjectName("categoryBadge")
        cat_badge.setStyleSheet(
            f"color: {fg_col}; background-color: {bg_col}; border: 1px solid {border_col};"
        )
        badges_layout.addWidget(cat_badge)

        if product.color and product.color.lower() in COLOR_CHIPS:
            chip_text, chip_color = COLOR_CHIPS[product.color.lower()]
            color_badge = QLabel(chip_text)
            color_badge.setObjectName("colorBadge")
            color_badge.setStyleSheet(f"color: {chip_color};")
            badges_layout.addWidget(color_badge)

        badges_layout.addStretch()
        content_v_layout.addLayout(badges_layout)

        # 2. Product Title (Full-width, word wrapped)
        title_label = QLabel(product.name)
        title_label.setObjectName("productTitle")
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        content_v_layout.addWidget(title_label)

        # 3. Description (Full-width, word wrapped)
        if product.description:
            desc_label = QLabel(product.description)
            desc_label.setObjectName("productDesc")
            desc_label.setWordWrap(True)
            desc_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            content_v_layout.addWidget(desc_label)

        # 4. Action Buttons Row
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)

        self.lens_btn = QPushButton("Google Lens")
        self.lens_btn.setProperty("class", "accentBtn")
        self.lens_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lens_btn.setToolTip("Upload crop & search exact visual matches in Google Lens")
        self.lens_btn.clicked.connect(self._on_google_lens_clicked)
        actions_layout.addWidget(self.lens_btn)

        amazon_btn = QPushButton("Amazon.in")
        amazon_btn.setProperty("class", "warmBtn")
        amazon_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        amazon_btn.setToolTip(f"Search '{product.query}' on Amazon India (amazon.in)")
        amazon_btn.clicked.connect(lambda: open_browser_url(product.amazon_url))
        actions_layout.addWidget(amazon_btn)

        google_shop_btn = QPushButton("Google Shop")
        google_shop_btn.setProperty("class", "neutralBtn")
        google_shop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        google_shop_btn.setToolTip(f"Find '{product.query}' on Google Shopping")
        google_shop_btn.clicked.connect(lambda: open_browser_url(product.google_shopping_url))
        actions_layout.addWidget(google_shop_btn)

        actions_layout.addStretch()
        content_v_layout.addLayout(actions_layout)

        main_h_layout.addLayout(content_v_layout)

    def _on_google_lens_clicked(self) -> None:
        """Upload visual crop directly to Google Lens and open search results."""
        self.lens_btn.setText("Uploading to Lens...")
        self.lens_btn.setEnabled(False)

        # Copy crop image to clipboard on GUI thread
        with contextlib.suppress(Exception):
            if self.product.crop_path and Path(self.product.crop_path).is_file():
                qimg = QImage(self.product.crop_path)
                if not qimg.isNull():
                    clipboard = QGuiApplication.clipboard()
                    if clipboard is not None:
                        clipboard.setImage(qimg)

        def worker() -> None:
            search_google_lens(self.product.crop_path, self.product.query)
            self.lens_ready.emit()

        threading.Thread(target=worker, daemon=True).start()

    def _on_lens_ready(self) -> None:
        self.lens_btn.setText("Opened in Browser ✓")
        self.lens_btn.setEnabled(True)
        QTimer.singleShot(2500, lambda: self.lens_btn.setText("Google Lens"))


class ProductPanel(QWidget):
    """Section displaying recognizable scene products, apparel, electronics, and shopping links."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # Banner Header
        self.banner = QFrame()
        self.banner.setObjectName("sectionBanner")
        banner_layout = QVBoxLayout(self.banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        banner_layout.setSpacing(2)

        self.title_label = QLabel("PRODUCTS & GEAR")
        self.title_label.setObjectName("sectionHeader")
        banner_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Recognizable clothing, screens, and equipment in this scene.")
        self.subtitle_label.setObjectName("emptyText")
        banner_layout.addWidget(self.subtitle_label)

        main_layout.addWidget(self.banner)

        # Scroll Area for Product Cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 4, 2, 4)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll_area)

    def update_content(
        self,
        products: list[ProductMatch],
        detections: list[Detection] | None = None,
    ) -> None:
        """Populate the panel with detected products."""
        # Clear existing cards
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        if products:
            self.subtitle_label.setText(
                f"Found {len(products)} recognizable items in this scene."
            )
            for prod in products:
                card = ProductCard(prod)
                self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        else:
            self.subtitle_label.setText("No recognizable products detected in this frame.")
            empty_frame = QFrame()
            empty_frame.setObjectName("emptyFrame")
            empty_layout = QVBoxLayout(empty_frame)
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            msg = QLabel(
                "No recognizable products or apparel in this frame.\n"
                "Pause on scenes featuring clothing, electronics, or gear."
            )
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setObjectName("emptyText")
            empty_layout.addWidget(msg)

            self.cards_layout.insertWidget(0, empty_frame)
