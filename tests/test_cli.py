"""Smoke tests for the CLI surface (no VLC, no models needed)."""

from __future__ import annotations

from pathlib import Path

import pytest

from frameshot.__main__ import run


def test_init_config_writes_file(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    assert run(["init-config", "--config", str(target)]) == 0
    assert target.is_file()
    assert "vlc:" in target.read_text(encoding="utf-8")


def test_init_config_refuses_to_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text("existing", encoding="utf-8")
    assert run(["init-config", "--config", str(target)]) == 1
    assert target.read_text(encoding="utf-8") == "existing"


def test_bad_config_returns_exit_code_2(tmp_path: Path) -> None:
    bad = tmp_path / "config.yaml"
    bad.write_text("vlc:\n  port: 0\n", encoding="utf-8")
    assert run(["doctor", "--config", str(bad)]) == 2


def test_doctor_runs_without_vlc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FRAMESHOT_CONFIG", raising=False)
    # Only assert that it completes and reports a value; environment-dependent.
    assert run(["doctor"]) in (0, 1)
