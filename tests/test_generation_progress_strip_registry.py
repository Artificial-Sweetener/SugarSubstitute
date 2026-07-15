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

"""Contract tests for selected generation progress projection mirroring."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QApplication

from substitute.application.generation.progress_service import ProgressViewState
from substitute.presentation.shell.generation_progress_strip import (
    GenerationProgressStrip,
)
from substitute.presentation.shell.generation_progress_strip_registry import (
    GenerationProgressStripRegistry,
)
from substitute.presentation.shell.progress_projection import ProgressProjectionMode


def test_progress_registry_replays_latest_selected_projection_to_late_strip() -> None:
    """Late-registered strips should receive the current selected projection."""

    _app()
    registry = GenerationProgressStripRegistry()
    strip = GenerationProgressStrip()

    registry.apply_progress_view(
        ProgressViewState(show_overlay=True, workflow_value=20, sampler_value=40)
    )
    registry.register(strip, visible_gate=lambda: True)

    assert strip.workflow_bar.value() == 20
    assert strip.sampler_bar.value() == 40
    assert strip.isHidden() is False


def test_progress_registry_respects_local_visibility_gate() -> None:
    """The reveal gate should hide selected progress even while active."""

    _app()
    registry = GenerationProgressStripRegistry()
    strip = GenerationProgressStrip()
    revealed = False
    registry.register(strip, visible_gate=lambda: revealed)

    registry.apply_progress_view(
        ProgressViewState(show_overlay=True, workflow_value=10, sampler_value=12)
    )
    assert strip.isHidden() is True

    revealed = True
    registry.refresh_visibility(strip)

    assert strip.isHidden() is False


def test_progress_registry_unregister_stops_future_updates() -> None:
    """Unregistered strips should stop receiving selected projection updates."""

    _app()
    registry = GenerationProgressStripRegistry()
    strip = GenerationProgressStrip()
    registry.register(strip, visible_gate=lambda: True)
    registry.apply_progress_view(
        ProgressViewState(show_overlay=True, workflow_value=15, sampler_value=30)
    )

    registry.unregister(strip)
    registry.apply_progress_view(
        ProgressViewState(show_overlay=True, workflow_value=80, sampler_value=90)
    )

    assert strip.workflow_bar.value() == 15
    assert strip.sampler_bar.value() == 30
    assert strip.isHidden() is True


def test_progress_registry_replays_late_strip_without_animation() -> None:
    """Late strip registration should snap to the latest selected projection."""

    _app()
    registry = GenerationProgressStripRegistry()
    strip = GenerationProgressStrip()

    registry.apply_progress_view(
        ProgressViewState(show_overlay=True, workflow_value=64, sampler_value=12),
        mode=ProgressProjectionMode.LIVE_UPDATE,
    )
    registry.register(strip, visible_gate=lambda: True)

    assert strip.workflow_bar.value() == 64
    assert strip.sampler_bar.value() == 12
    assert strip.workflow_bar.isUseAni() is True
    assert strip.sampler_bar.isUseAni() is True


def _app() -> QApplication:
    """Return the shared QApplication used by registry tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)
