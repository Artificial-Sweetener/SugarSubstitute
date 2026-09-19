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

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QWidget

from sugarsubstitute_shared import qt_surface_readiness as application_readiness
from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessSurface,
    READINESS_PATH_ENV,
    READINESS_SCHEMA_VERSION,
    READINESS_TOKEN_ENV,
)
from tests.support.qt.lifecycle import ensure_qt_application


def test_readiness_receipt_is_queued_after_shell_reveal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Publish the launch token through queued Qt work after a shell reveal."""

    callbacks: list[Callable[[], None]] = []
    readiness_path = tmp_path / "launcher" / "readiness" / "launch.json"
    monkeypatch.setenv(READINESS_PATH_ENV, str(readiness_path))
    monkeypatch.setenv(READINESS_TOKEN_ENV, "launch-token")
    monkeypatch.setattr(
        application_readiness,
        "run_after_surface_paint",
        lambda _window, callback: callbacks.append(callback),
    )

    scheduled = application_readiness.schedule_surface_readiness_receipt(
        surface=ApplicationReadinessSurface.MAIN_SHELL,
        window=object(),
    )

    assert scheduled is True
    assert not readiness_path.exists()
    assert len(callbacks) == 1
    callbacks[0]()
    payload = json.loads(readiness_path.read_text(encoding="utf-8"))
    assert payload == {
        "parent_pid": os.getppid(),
        "pid": os.getpid(),
        "schema_version": READINESS_SCHEMA_VERSION,
        "surface": "main_shell",
        "token": "launch-token",
        "milestones": [
            "process_started",
            "surface_painted",
            "event_loop_turn_completed",
        ],
    }
    assert os.environ[READINESS_PATH_ENV] == str(readiness_path)
    assert os.environ[READINESS_TOKEN_ENV] == "launch-token"


def test_readiness_receipt_waits_for_ordered_surface_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Publish readiness only after its post-paint prerequisite completes."""

    callbacks: list[Callable[[], None]] = []
    events: list[str] = []
    readiness_path = (tmp_path / "launcher" / "ordered.json").resolve()
    monkeypatch.setenv(READINESS_PATH_ENV, str(readiness_path))
    monkeypatch.setenv(READINESS_TOKEN_ENV, "launch-token")
    monkeypatch.setattr(
        application_readiness,
        "run_after_surface_paint",
        lambda _window, callback: callbacks.append(callback),
    )

    def complete_splash_handoff() -> None:
        """Prove the readiness receipt does not exist during splash handoff."""

        assert not readiness_path.exists()
        events.append("splash_closed")

    assert application_readiness.schedule_main_shell_readiness_receipt(
        object(),
        before_publish=complete_splash_handoff,
    )

    callbacks[0]()

    assert events == ["splash_closed"]
    assert readiness_path.is_file()


def test_readiness_token_survives_onboarding_to_main_shell_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Publish the authenticated receipt through onboarding-to-shell handoff."""

    callbacks: list[Callable[[], None]] = []
    readiness_path = (tmp_path / "launcher" / "readiness" / "launch.json").resolve()
    monkeypatch.setenv(READINESS_PATH_ENV, str(readiness_path))
    monkeypatch.setenv(READINESS_TOKEN_ENV, "launch-token")
    monkeypatch.setattr(
        application_readiness,
        "run_after_surface_paint",
        lambda _window, callback: callbacks.append(callback),
    )

    assert application_readiness.schedule_surface_readiness_receipt(
        surface=ApplicationReadinessSurface.ONBOARDING,
        window=object(),
    )
    callbacks.pop(0)()
    assert (
        json.loads(readiness_path.read_text(encoding="utf-8"))["surface"]
        == "onboarding"
    )

    assert application_readiness.schedule_surface_readiness_receipt(
        surface=ApplicationReadinessSurface.MAIN_SHELL,
        window=object(),
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
    monkeypatch.setenv(READINESS_PATH_ENV, "relative.txt")
    monkeypatch.setenv(READINESS_TOKEN_ENV, "launch-token")
    monkeypatch.setattr(
        application_readiness,
        "run_after_surface_paint",
        lambda _window, callback: callbacks.append(callback),
    )

    assert (
        application_readiness.schedule_surface_readiness_receipt(
            surface=ApplicationReadinessSurface.ONBOARDING,
            window=object(),
        )
        is False
    )
    assert callbacks == []


def test_real_readiness_receipt_waits_for_the_exact_window_to_paint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A constructed or merely scheduled shell must not count as ready."""

    application = ensure_qt_application()
    readiness_path = (tmp_path / "launcher" / "readiness" / "paint.json").resolve()
    monkeypatch.setenv(READINESS_PATH_ENV, str(readiness_path))
    monkeypatch.setenv(READINESS_TOKEN_ENV, "paint-token")
    window = QWidget()

    assert application_readiness.schedule_surface_readiness_receipt(
        surface=ApplicationReadinessSurface.MAIN_SHELL,
        window=window,
    )
    QCoreApplication.processEvents()
    assert not readiness_path.exists()

    window.show()
    QCoreApplication.processEvents()
    QCoreApplication.processEvents()

    assert json.loads(readiness_path.read_text(encoding="utf-8"))["surface"] == (
        "main_shell"
    )
    window.close()
    application.processEvents()
