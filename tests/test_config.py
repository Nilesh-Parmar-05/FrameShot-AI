"""Tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from frameshot.config import (
    CONFIG_ENV_VAR,
    AppConfig,
    ConfigError,
    DifficultyLevel,
    ModelProfile,
    resolve_config_path,
)


def test_defaults_are_offline_first() -> None:
    cfg = AppConfig()
    assert cfg.online.enabled is False
    assert cfg.vlc.host == "127.0.0.1"
    assert cfg.vlc.port == 8080
    assert cfg.analysis.difficulty_level is DifficultyLevel.INTERMEDIATE
    assert cfg.analysis.model_profile is ModelProfile.BALANCED


def test_poll_interval_can_meet_auto_dismiss_budget() -> None:
    # PRD §8: overlay hides within 200 ms of resume, so polling must be <= 200 ms.
    assert AppConfig().vlc.poll_interval_ms <= 200


def test_load_without_file_returns_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(CONFIG_ENV_VAR, raising=False)
    assert resolve_config_path(None) is None
    assert AppConfig.load() == AppConfig()


def test_load_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "vlc:\n"
        "  port: 9090\n"
        "  password: secret\n"
        "analysis:\n"
        "  difficulty_level: advanced\n"
        "  confidence_threshold: 0.85\n",
        encoding="utf-8",
    )
    cfg = AppConfig.load(path)
    assert cfg.vlc.port == 9090
    assert cfg.vlc.password == "secret"
    assert cfg.analysis.difficulty_level is DifficultyLevel.ADVANCED
    assert cfg.analysis.confidence_threshold == 0.85
    # unspecified keys keep their defaults
    assert cfg.vlc.host == "127.0.0.1"


def test_example_config_is_valid() -> None:
    root = Path(__file__).resolve().parent.parent
    cfg = AppConfig.load(root / "config.example.yaml")
    assert cfg.vlc.password == "frameshot"
    assert cfg.paths.snapshot_dir.parts[-1] == "snapshots"


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("vlc:\n  prot: 8080\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid config"):
        AppConfig.load(path)


def test_out_of_range_value_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("vlc:\n  port: 70000\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        AppConfig.load(path)


def test_malformed_yaml_raises(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("vlc: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        AppConfig.load(path)


def test_missing_explicit_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        AppConfig.load(tmp_path / "nope.yaml")


def test_env_var_missing_file_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_ENV_VAR, str(tmp_path / "nope.yaml"))
    with pytest.raises(ConfigError, match=CONFIG_ENV_VAR):
        resolve_config_path(None)


def test_round_trip_save_and_load(tmp_path: Path) -> None:
    cfg = AppConfig()
    cfg.vlc.port = 8123
    cfg.analysis.model_profile = ModelProfile.LITE
    path = cfg.save(tmp_path / "nested" / "config.yaml")
    assert AppConfig.load(path) == cfg
