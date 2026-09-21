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

"""Test deferred projection geometry reuse warming."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QObject

from substitute.presentation.editor.prompt_editor.projection.geometry_reuse_warmer import (
    PromptProjectionGeometryReuseWarmer,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp


def test_geometry_reuse_warmer_coalesces_eligible_requests() -> None:
    """Repeated projected requests should warm the current index once."""

    ensure_qapp()
    state = {"available": True, "projected": True}
    warms: list[None] = []
    parent = QObject()
    owner = PromptProjectionGeometryReuseWarmer(
        is_available=lambda: state["available"],
        is_projected=lambda: state["projected"],
        prewarm=lambda: warms.append(None),
        parent=parent,
    )

    owner.schedule(reason="first")
    owner.schedule(reason="coalesced")
    QCoreApplication.processEvents()

    assert warms == [None]


def test_geometry_reuse_warmer_rejects_ineligible_requests() -> None:
    """Raw mode and unavailable owners should not queue index work."""

    ensure_qapp()
    state = {"available": True, "projected": False}
    warms: list[None] = []
    parent = QObject()
    owner = PromptProjectionGeometryReuseWarmer(
        is_available=lambda: state["available"],
        is_projected=lambda: state["projected"],
        prewarm=lambda: warms.append(None),
        parent=parent,
    )

    owner.schedule(reason="raw")
    state["projected"] = True
    state["available"] = False
    owner.schedule(reason="destroyed")
    QCoreApplication.processEvents()

    assert warms == []
