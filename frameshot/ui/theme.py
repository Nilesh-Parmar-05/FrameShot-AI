"""FrameShot-AI Design System Tokens & QSS Compiler.

Centralized source of truth for colors, typography, radii, spacing, and
desktop stylesheet rules. Replaces scattered inline styles.
"""

from __future__ import annotations


class Theme:
    """Design tokens following dark mode elevation principles."""

    # Surfaces
    BG_BASE = "#0c0f14"
    BG_CARD = "#141820"
    BG_ELEVATED = "#1c2230"
    BG_HOVER = "#242c3e"
    BG_ACTIVE = "#2d384e"
    BG_INPUT = "#10141c"

    # Borders
    BORDER_SUBTLE = "#1e2638"
    BORDER_DEFAULT = "#2a364d"
    BORDER_FOCUS = "#4f8ff7"

    # Text hierarchy
    TEXT_PRIMARY = "#e8ecf4"
    TEXT_SECONDARY = "#8b95a8"
    TEXT_TERTIARY = "#5a6478"
    TEXT_INVERSE = "#0c0f14"

    # Accent (single coherent hue: electric blue)
    ACCENT_DEFAULT = "#4f8ff7"
    ACCENT_HOVER = "#6ba1ff"
    ACCENT_MUTED = "rgba(79, 143, 247, 0.12)"
    ACCENT_BORDER = "rgba(79, 143, 247, 0.32)"
    ACCENT_STRONG = "rgba(79, 143, 247, 0.24)"

    # Semantic states
    DANGER = "#e5534b"
    DANGER_MUTED = "rgba(229, 83, 75, 0.12)"
    DANGER_HOVER = "rgba(229, 83, 75, 0.24)"

    WARNING = "#f0a030"
    WARNING_MUTED = "rgba(240, 160, 48, 0.12)"
    WARNING_BORDER = "rgba(240, 160, 48, 0.32)"
    WARNING_HOVER = "rgba(240, 160, 48, 0.24)"

    SUCCESS = "#3dd68c"
    SUCCESS_MUTED = "rgba(61, 214, 140, 0.12)"

    # Typography
    FONT_FAMILY = (
        "-apple-system, 'Inter', 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif"
    )

    # Radii
    RADIUS_SM = "4px"
    RADIUS_MD = "8px"
    RADIUS_LG = "12px"

    # Spacing (4px grid)
    SPACE_2XS = "2px"
    SPACE_XS = "4px"
    SPACE_SM = "8px"
    SPACE_MD = "12px"
    SPACE_LG = "16px"
    SPACE_XL = "20px"


# Category accent mappings for detections & products
CATEGORY_COLORS: dict[str, tuple[str, str, str]] = {
    # category: (foreground_hex, background_rgba, border_rgba)
    "clothing": ("#a78bfa", "rgba(167, 139, 250, 0.12)", "rgba(167, 139, 250, 0.30)"),
    "electronics": ("#60a5fa", "rgba(96, 165, 250, 0.12)", "rgba(96, 165, 250, 0.30)"),
    "furniture": ("#f59e0b", "rgba(245, 158, 11, 0.12)", "rgba(245, 158, 11, 0.30)"),
    "vehicle": ("#fbbf24", "rgba(251, 191, 36, 0.12)", "rgba(251, 191, 36, 0.30)"),
    "person": ("#38bdf8", "rgba(56, 189, 248, 0.12)", "rgba(56, 189, 248, 0.30)"),
    "animal": ("#34d399", "rgba(52, 211, 153, 0.12)", "rgba(52, 211, 153, 0.30)"),
    "appliance": ("#2dd4bf", "rgba(45, 212, 191, 0.12)", "rgba(45, 212, 191, 0.30)"),
    "gear": ("#4f8ff7", "rgba(79, 143, 247, 0.12)", "rgba(79, 143, 247, 0.30)"),
    "accessories": ("#e879f9", "rgba(232, 121, 249, 0.12)", "rgba(232, 121, 249, 0.30)"),
    "object": ("#8b95a8", "rgba(139, 149, 168, 0.12)", "rgba(139, 149, 168, 0.30)"),
}

# Standardized garment color chips
COLOR_CHIPS: dict[str, tuple[str, str]] = {
    "white": ("White", "#f8fafc"),
    "black": ("Black", "#94a3b8"),
    "grey": ("Grey", "#cbd5e1"),
    "navy": ("Navy Blue", "#60a5fa"),
    "blue": ("Blue", "#38bdf8"),
    "teal": ("Teal", "#2dd4bf"),
    "green": ("Green", "#34d399"),
    "yellow": ("Yellow", "#fbbf24"),
    "orange": ("Orange", "#fb923c"),
    "red": ("Red", "#f87171"),
    "maroon": ("Maroon", "#e11d48"),
    "purple": ("Purple", "#a78bfa"),
    "brown": ("Brown", "#d97706"),
}


def compile_stylesheet() -> str:
    """Compile the master QSS stylesheet with design system tokens."""
    t = Theme
    return f"""
    /* --- Base Resets & Global Font --- */
    QWidget {{
        font-family: {t.FONT_FAMILY};
        color: {t.TEXT_PRIMARY};
    }}

    /* --- Central Overlay Container --- */
    #centralCard {{
        background-color: {t.BG_CARD};
        border: 1px solid {t.BORDER_SUBTLE};
        border-radius: {t.RADIUS_LG};
    }}

    #appTitle {{
        color: {t.TEXT_PRIMARY};
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.3px;
    }}

    #closeBtn {{
        background: transparent;
        color: {t.TEXT_TERTIARY};
        font-size: 16px;
        font-weight: 400;
        border: none;
        border-radius: {t.RADIUS_SM};
        padding: 0px 4px;
        min-width: 22px;
        min-height: 22px;
    }}
    #closeBtn:hover {{
        color: {t.DANGER};
        background-color: {t.DANGER_MUTED};
    }}
    #closeBtn:pressed {{
        background-color: {t.DANGER_HOVER};
    }}

    /* --- Tab Navigation --- */
    QTabWidget::pane {{
        border: none;
        background: transparent;
    }}
    QTabBar::tab {{
        color: {t.TEXT_SECONDARY};
        background: transparent;
        font-size: 13px;
        font-weight: 500;
        padding: 6px 14px;
        margin-right: 6px;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{
        color: {t.ACCENT_DEFAULT};
        border-bottom: 2px solid {t.ACCENT_DEFAULT};
    }}
    QTabBar::tab:hover:!selected {{
        color: {t.TEXT_PRIMARY};
    }}

    /* --- Subtitle & Section Banners --- */
    #subtitleBanner, #sectionBanner {{
        background-color: {t.BG_ELEVATED};
        border: 1px solid {t.BORDER_SUBTLE};
        border-radius: {t.RADIUS_MD};
    }}

    #subtitleText {{
        color: {t.TEXT_PRIMARY};
        font-size: 13px;
        font-weight: 400;
        line-height: 1.4;
    }}

    #sectionHeader {{
        color: {t.TEXT_SECONDARY};
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.4px;
        text-transform: uppercase;
    }}

    /* --- Content Cards (Word & Product) --- */
    #wordCard, #productCard {{
        background-color: {t.BG_ELEVATED};
        border: 1px solid {t.BORDER_SUBTLE};
        border-radius: {t.RADIUS_MD};
    }}
    #wordCard:hover, #productCard:hover {{
        background-color: {t.BG_HOVER};
        border-color: {t.BORDER_DEFAULT};
    }}

    #wordTitle, #productTitle {{
        color: {t.TEXT_PRIMARY};
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.2px;
    }}

    #definitionText, #productDesc {{
        color: {t.TEXT_PRIMARY};
        font-size: 12px;
        line-height: 1.45;
    }}

    #synonymsText {{
        color: {t.TEXT_SECONDARY};
        font-size: 11px;
    }}

    /* --- Badges --- */
    #ipaBadge {{
        color: {t.ACCENT_DEFAULT};
        background-color: {t.ACCENT_MUTED};
        border-radius: {t.RADIUS_SM};
        padding: 2px 6px;
        font-size: 11px;
        font-weight: 500;
    }}

    #posBadge {{
        color: #a78bfa;
        background-color: rgba(167, 139, 250, 0.12);
        border-radius: {t.RADIUS_SM};
        padding: 2px 6px;
        font-size: 11px;
        font-style: italic;
    }}

    #categoryBadge {{
        border-radius: {t.RADIUS_SM};
        padding: 2px 6px;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.4px;
    }}

    #colorBadge {{
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid {t.BORDER_SUBTLE};
        border-radius: {t.RADIUS_SM};
        padding: 1px 6px;
        font-size: 10px;
        font-weight: 500;
    }}

    /* --- Buttons & Action Variants --- */
    #diveBtn, QPushButton.accentBtn {{
        background-color: {t.ACCENT_MUTED};
        color: {t.ACCENT_DEFAULT};
        border: 1px solid {t.ACCENT_BORDER};
        border-radius: {t.RADIUS_SM};
        padding: 3px 8px;
        font-size: 11px;
        font-weight: 500;
    }}
    #diveBtn:hover, QPushButton.accentBtn:hover {{
        background-color: {t.ACCENT_STRONG};
        color: #ffffff;
    }}
    #diveBtn:pressed, QPushButton.accentBtn:pressed {{
        background-color: {t.ACCENT_DEFAULT};
        color: {t.TEXT_INVERSE};
    }}

    QPushButton.warmBtn {{
        background-color: {t.WARNING_MUTED};
        color: {t.WARNING};
        border: 1px solid {t.WARNING_BORDER};
        border-radius: {t.RADIUS_SM};
        padding: 3px 8px;
        font-size: 11px;
        font-weight: 500;
    }}
    QPushButton.warmBtn:hover {{
        background-color: {t.WARNING_HOVER};
        color: #ffffff;
    }}

    QPushButton.neutralBtn {{
        background-color: rgba(139, 149, 168, 0.10);
        color: {t.TEXT_SECONDARY};
        border: 1px solid rgba(139, 149, 168, 0.24);
        border-radius: {t.RADIUS_SM};
        padding: 3px 8px;
        font-size: 11px;
        font-weight: 500;
    }}
    QPushButton.neutralBtn:hover {{
        background-color: rgba(139, 149, 168, 0.20);
        color: {t.TEXT_PRIMARY};
    }}

    /* --- Deep Dive / Wikipedia Disclosure Box --- */
    #diveBox, #wikiBox {{
        background-color: {t.BG_BASE};
        border: 1px dashed {t.BORDER_DEFAULT};
        border-radius: {t.RADIUS_MD};
    }}

    #diveContent, #wikiExtract {{
        color: {t.TEXT_SECONDARY};
        font-size: 12px;
        line-height: 1.45;
    }}

    #wikiTitle {{
        color: {t.ACCENT_DEFAULT};
        font-size: 13px;
        font-weight: 600;
    }}

    /* --- Input Fields & Search --- */
    QLineEdit#searchInput {{
        background-color: {t.BG_INPUT};
        border: 1px solid {t.BORDER_DEFAULT};
        border-radius: {t.RADIUS_SM};
        padding: 6px 10px;
        color: {t.TEXT_PRIMARY};
        font-size: 12px;
    }}
    QLineEdit#searchInput:focus {{
        border-color: {t.BORDER_FOCUS};
    }}

    /* --- Journal Cards --- */
    #journalCard {{
        background-color: {t.BG_ELEVATED};
        border: 1px solid {t.BORDER_SUBTLE};
        border-radius: {t.RADIUS_MD};
    }}
    #journalCard:hover {{
        background-color: {t.BG_HOVER};
        border-color: {t.BORDER_DEFAULT};
    }}

    #deleteBtn {{
        background: transparent;
        color: {t.TEXT_TERTIARY};
        border: 1px solid transparent;
        border-radius: {t.RADIUS_SM};
        padding: 2px 6px;
        font-size: 11px;
    }}
    #deleteBtn:hover {{
        color: {t.DANGER};
        background-color: {t.DANGER_MUTED};
        border-color: {t.DANGER};
    }}

    /* --- Empty States --- */
    #emptyFrame {{
        background-color: rgba(28, 34, 48, 0.40);
        border: 1px dashed {t.BORDER_DEFAULT};
        border-radius: {t.RADIUS_MD};
        padding: 16px;
    }}
    #emptyText {{
        color: {t.TEXT_TERTIARY};
        font-size: 12px;
        font-style: italic;
        line-height: 1.4;
    }}

    /* --- Scrollbars --- */
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 0px;
        border-radius: 3px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.BORDER_DEFAULT};
        border-radius: 3px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t.TEXT_TERTIARY};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
        background: transparent;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    """

