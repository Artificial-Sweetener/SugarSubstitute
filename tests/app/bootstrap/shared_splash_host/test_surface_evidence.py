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

"""Verify explicit headless splash-surface qualification evidence."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QWidget

from substitute.app.bootstrap import shared_splash_host
from tests.support.qt.lifecycle import ensure_qt_application, widget_root_scope


def test_surface_evidence_records_the_visible_top_level_splash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Qualification should observe the real Qt surface after it is shown."""

    application = ensure_qt_application()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SUGAR_SUBSTITUTE_SPLASH_SURFACE_EVIDENCE", "1")
    monkeypatch.setenv(
        "SUGAR_SUBSTITUTE_SPLASH_REQUESTED_MONOTONIC_NS",
        "120000000",
    )
    with widget_root_scope() as owner:
        splash = owner.own(QWidget())
        splash.show()
        application.processEvents()

        shared_splash_host._write_surface_evidence(
            app=application,
            splash=splash,
            first_paint_monotonic_ns=123_000_000,
        )

    evidence_path = (
        tmp_path / "user" / "qualification-splash-surfaces" / f"{os.getpid()}.json"
    )
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["host_pid"] == os.getpid()
    assert payload["first_paint_confirmed"] is True
    assert payload["launch_to_first_paint_ms"] == 3.0
    assert payload["splash_is_visible"] is True
    assert payload["top_level_surface_count"] >= 1
    assert payload["visible_top_level_surface_count"] >= 1
