"""Application configuration: schema, loading, and validation.

Mirrors the schema documented in ``architecture.md`` §8, with two deliberate
adjustments:

* ``vlc.poll_interval_ms`` defaults to 200 ms. PRD §8 requires the overlay to
  hide within 200 ms of resuming playback, which a 500 ms poll cannot meet.
* ``paths.vocab_journal`` was dropped. ``architecture.md`` §7.3 puts the
  vocabulary journal in the main database, so a second DB path would be a
  second source of truth.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

CONFIG_ENV_VAR = "FRAMESHOT_CONFIG"
DEFAULT_CONFIG_FILENAME = "config.yaml"


class ConfigError(Exception):
    """Raised when a configuration file is missing, malformed, or invalid."""


class DifficultyLevel(StrEnum):
    """Vocabulary level used to decide which words are "hard" (FR-25)."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ModelProfile(StrEnum):
    """Vision model bundle (architecture.md §5.4)."""

    LITE = "lite"
    BALANCED = "balanced"
    FULL = "full"


class OverlayPosition(StrEnum):
    """Where the overlay is anchored relative to the VLC window."""

    LEFT = "left"
    RIGHT = "right"
    BOTTOM = "bottom"
    FULLSCREEN = "fullscreen"


class Theme(StrEnum):
    DARK = "dark"
    LIGHT = "light"
    AUTO = "auto"


class _Section(BaseModel):
    """Base for config sections: reject unknown keys so typos are caught."""

    model_config = ConfigDict(extra="forbid")


class VLCConfig(_Section):
    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1, le=65535)
    password: str = ""
    poll_interval_ms: int = Field(default=200, ge=50, le=5000)
    request_timeout_s: float = Field(default=2.0, gt=0.0, le=30.0)


class AnalysisConfig(_Section):
    difficulty_level: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    model_profile: ModelProfile = ModelProfile.BALANCED


class OverlayConfig(_Section):
    opacity: float = Field(default=0.85, ge=0.0, le=1.0)
    position: OverlayPosition = OverlayPosition.RIGHT
    hotkey: str = "Ctrl+Shift+F"
    auto_dismiss: bool = True
    theme: Theme = Theme.DARK


class OnlineServicesConfig(_Section):
    wikipedia: bool = True
    wiktionary: bool = True
    product_lookup: bool = False


class OnlineConfig(_Section):
    """Online enrichment is opt-in (FR-53, NFR-04)."""

    enabled: bool = False
    cache_ttl_days: int = Field(default=7, ge=0, le=365)
    services: OnlineServicesConfig = Field(default_factory=OnlineServicesConfig)


class PathsConfig(_Section):
    models_dir: Path = Path("models")
    database: Path = Path("data/frameshot.db")
    word_freq: Path = Path("data/word_frequency.db")
    snapshot_dir: Path = Path("data/snapshots")
    log_dir: Path = Path("logs")


class AppConfig(_Section):
    """Root configuration object."""

    vlc: VLCConfig = Field(default_factory=VLCConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    overlay: OverlayConfig = Field(default_factory=OverlayConfig)
    online: OnlineConfig = Field(default_factory=OnlineConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

    # ------------------------------------------------------------ loading

    @classmethod
    def load(cls, path: str | Path | None = None) -> AppConfig:
        """Load configuration, falling back to defaults when no file exists.

        Resolution order: explicit ``path`` -> ``$FRAMESHOT_CONFIG`` ->
        ``./config.yaml`` -> built-in defaults.
        """
        resolved = resolve_config_path(path)
        if resolved is None:
            return cls()
        return cls.from_yaml(resolved)

    @classmethod
    def from_yaml(cls, path: str | Path) -> AppConfig:
        """Parse and validate a YAML configuration file."""
        file_path = Path(path)
        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigError(f"cannot read config file {file_path}: {exc}") from exc

        try:
            raw: Any = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid YAML in {file_path}: {exc}") from exc

        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ConfigError(f"config root must be a mapping, got {type(raw).__name__}")

        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            raise ConfigError(f"invalid config in {file_path}:\n{exc}") from exc

    # ------------------------------------------------------------ saving

    def to_dict(self) -> dict[str, Any]:
        """JSON/YAML-safe representation (enums become their values)."""
        return self.model_dump(mode="json")

    def save(self, path: str | Path) -> Path:
        """Write this configuration back out as YAML."""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return file_path


def resolve_config_path(path: str | Path | None = None) -> Path | None:
    """Return the config file to use, or ``None`` to mean "use defaults".

    An explicitly requested (argument or env var) file must exist; the implicit
    ``./config.yaml`` is optional.
    """
    if path is not None:
        explicit = Path(path)
        if not explicit.is_file():
            raise ConfigError(f"config file not found: {explicit}")
        return explicit

    from_env = os.environ.get(CONFIG_ENV_VAR)
    if from_env:
        env_path = Path(from_env)
        if not env_path.is_file():
            raise ConfigError(f"{CONFIG_ENV_VAR} points to a missing file: {env_path}")
        return env_path

    implicit = Path.cwd() / DEFAULT_CONFIG_FILENAME
    if implicit.is_file():
        return implicit

    return None
