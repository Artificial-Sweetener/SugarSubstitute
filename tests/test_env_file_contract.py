#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Contract tests for dependency-free .env loading."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pytest import LogCaptureFixture

from substitute.app.bootstrap.env_file import load_env_file


def test_missing_env_file_returns_missing_result(tmp_path: Path) -> None:
    """Missing .env files should be non-fatal."""
    result = load_env_file(tmp_path / ".env")

    assert result.missing is True
    assert result.loaded == 0
    assert result.skipped_existing == 0
    assert result.malformed == 0


def test_env_file_loads_basic_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Basic KEY=value lines should populate the process environment."""
    monkeypatch.delenv("SUGAR_TRACE_ONE", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SUGAR_TRACE_ONE=1\n", encoding="utf-8")

    result = load_env_file(env_file)

    assert result.missing is False
    assert result.loaded == 1
    assert os.environ["SUGAR_TRACE_ONE"] == "1"


def test_env_file_does_not_override_existing_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Real process environment values should win over .env entries."""
    monkeypatch.setenv("SUGAR_TRACE_EXISTING", "from-shell")
    env_file = tmp_path / ".env"
    env_file.write_text("SUGAR_TRACE_EXISTING=from-file\n", encoding="utf-8")

    result = load_env_file(env_file)

    assert result.loaded == 0
    assert result.skipped_existing == 1
    assert os.environ["SUGAR_TRACE_EXISTING"] == "from-shell"


def test_env_file_ignores_comments_and_blank_lines(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Comments and whitespace-only lines should not affect load counts."""
    monkeypatch.delenv("SUGAR_TRACE_TWO", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n  # comment\nSUGAR_TRACE_TWO=yes\n   \n",
        encoding="utf-8",
    )

    result = load_env_file(env_file)

    assert result.loaded == 1
    assert os.environ["SUGAR_TRACE_TWO"] == "yes"


def test_env_file_unwraps_single_and_double_quoted_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Simple quoted values should be unwrapped while preserving interior spaces."""
    monkeypatch.delenv("SUGAR_TRACE_SINGLE", raising=False)
    monkeypatch.delenv("SUGAR_TRACE_DOUBLE", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SUGAR_TRACE_SINGLE='  left and right  '\n"
        'SUGAR_TRACE_DOUBLE="quoted value"\n',
        encoding="utf-8",
    )

    result = load_env_file(env_file)

    assert result.loaded == 2
    assert os.environ["SUGAR_TRACE_SINGLE"] == "  left and right  "
    assert os.environ["SUGAR_TRACE_DOUBLE"] == "quoted value"


def test_env_file_supports_export_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An optional export prefix should be accepted for simple assignments."""
    monkeypatch.delenv("SUGAR_TRACE_EXPORTED", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("export SUGAR_TRACE_EXPORTED=on\n", encoding="utf-8")

    result = load_env_file(env_file)

    assert result.loaded == 1
    assert os.environ["SUGAR_TRACE_EXPORTED"] == "on"


def test_env_file_counts_malformed_lines_without_raising(
    caplog: LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """Malformed lines should warn and not stop later valid values from loading."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "not-an-assignment\nVALID_AFTER_BAD=1\nBROKEN='unterminated\n",
        encoding="utf-8",
    )

    result = load_env_file(env_file)

    assert result.loaded == 1
    assert result.malformed == 2
    assert "Ignoring malformed .env line" in caplog.text


def test_env_file_loads_without_bootstrap_objects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The loader should work before Qt or installation bootstrap exists."""
    monkeypatch.delenv("SUGAR_BOOTSTRAP_EARLY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SUGAR_BOOTSTRAP_EARLY=true\n", encoding="utf-8")

    result = load_env_file(env_file)

    assert result.loaded == 1
    assert os.environ["SUGAR_BOOTSTRAP_EARLY"] == "true"
