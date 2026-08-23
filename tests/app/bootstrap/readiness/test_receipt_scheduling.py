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

"""Test bootstrap scheduling of launcher-verifiable readiness receipts."""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path

from PySide6.QtCore import QTimer
import pytest

from substitute.app.bootstrap import application_readiness
from sugarsubstitute_shared.application_readiness import ApplicationReadinessSurface


def test_readiness_receipt_is_queued_after_shell_reveal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Publish the launch token through queued Qt work after a shell reveal."""

    callbacks: list[Callable[[], None]] = []
    readiness_path = tmp_path / "launcher" / "readiness" / "launch.json"
    monkeypatch.setenv(application_readiness.READINESS_PATH_ENV, str(readiness_path))
    monkeypatch.setenv(application_readiness.READINESS_TOKEN_ENV, "launch-token")
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        lambda delay, callback: callbacks.append(callback) if delay == 0 else None,
    )

    scheduled = application_readiness.schedule_application_readiness_receipt(
        surface=ApplicationReadinessSurface.MAIN_SHELL
    )

    assert scheduled is True
    assert not readiness_path.exists()
    assert len(callbacks) == 1
    callbacks[0]()
    payload = json.loads(readiness_path.read_text(encoding="utf-8"))
    assert payload == {
        "pid": os.getpid(),
        "schema_version": application_readiness.READINESS_SCHEMA_VERSION,
        "surface": "main_shell",
        "token": "launch-token",
    }
    assert os.environ[application_readiness.READINESS_PATH_ENV] == str(readiness_path)
    assert os.environ[application_readiness.READINESS_TOKEN_ENV] == "launch-token"


def test_readiness_token_survives_onboarding_to_main_shell_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Publish the authenticated receipt through onboarding-to-shell handoff."""

    callbacks: list[Callable[[], None]] = []
    readiness_path = (tmp_path / "launcher" / "readiness" / "launch.json").resolve()
    monkeypatch.setenv(application_readiness.READINESS_PATH_ENV, str(readiness_path))
    monkeypatch.setenv(application_readiness.READINESS_TOKEN_ENV, "launch-token")
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        lambda delay, callback: callbacks.append(callback) if delay == 0 else None,
    )

    assert application_readiness.schedule_application_readiness_receipt(
        surface=ApplicationReadinessSurface.ONBOARDING
    )
    callbacks.pop(0)()
    assert (
        json.loads(readiness_path.read_text(encoding="utf-8"))["surface"]
        == "onboarding"
    )

    assert application_readiness.schedule_application_readiness_receipt(
        surface=ApplicationReadinessSurface.MAIN_SHELL
    )
    callbacks.pop(0)()
    assert (
        json.loads(readiness_path.read_text(encoding="utf-8"))["surface"]
        == "main_shell"
    )


def test_readiness_receipt_requires_absolute_json_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject a relative caller-controlled path without scheduling a write."""

    callbacks: list[Callable[[], None]] = []
    monkeypatch.setenv(application_readiness.READINESS_PATH_ENV, "relative.txt")
    monkeypatch.setenv(application_readiness.READINESS_TOKEN_ENV, "launch-token")
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        lambda _delay, callback: callbacks.append(callback),
    )

    assert (
        application_readiness.schedule_application_readiness_receipt(
            surface=ApplicationReadinessSurface.ONBOARDING
        )
        is False
    )
    assert callbacks == []
