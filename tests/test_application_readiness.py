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

"""Tests for the launcher-verifiable application readiness receipt."""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path

from PySide6.QtCore import QTimer
import pytest

from substitute.app.bootstrap import application_readiness


def test_readiness_receipt_is_queued_after_shell_reveal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The app should publish the launch token through queued Qt work."""

    callbacks: list[Callable[[], None]] = []
    readiness_path = tmp_path / "launcher" / "readiness" / "launch.json"
    monkeypatch.setenv(
        application_readiness.READINESS_PATH_ENV,
        str(readiness_path),
    )
    monkeypatch.setenv(
        application_readiness.READINESS_TOKEN_ENV,
        "launch-token",
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        lambda delay, callback: callbacks.append(callback) if delay == 0 else None,
    )

    scheduled = application_readiness.schedule_application_readiness_receipt()

    assert scheduled is True
    assert not readiness_path.exists()
    assert len(callbacks) == 1
    callbacks[0]()
    payload = json.loads(readiness_path.read_text(encoding="utf-8"))
    assert payload == {
        "pid": os.getpid(),
        "schema_version": application_readiness.READINESS_SCHEMA_VERSION,
        "token": "launch-token",
    }
    assert application_readiness.READINESS_PATH_ENV not in os.environ
    assert application_readiness.READINESS_TOKEN_ENV not in os.environ


def test_readiness_receipt_requires_absolute_json_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An invalid caller-controlled path must not schedule a filesystem write."""

    callbacks: list[Callable[[], None]] = []
    monkeypatch.setenv(
        application_readiness.READINESS_PATH_ENV,
        "relative.txt",
    )
    monkeypatch.setenv(
        application_readiness.READINESS_TOKEN_ENV,
        "launch-token",
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        lambda _delay, callback: callbacks.append(callback),
    )

    assert application_readiness.schedule_application_readiness_receipt() is False
    assert callbacks == []
