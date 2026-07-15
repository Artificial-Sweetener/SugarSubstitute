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

"""Contract tests for shared generation progress strips."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QApplication, QLayout

from substitute.application.generation.progress_service import ProgressViewState
from substitute.presentation.shell.generation_progress_strip import (
    GenerationProgressStrip,
)
from substitute.presentation.shell.progress_projection import ProgressProjectionMode


def test_generation_progress_strip_builds_two_stacked_bars() -> None:
    """Progress strip should expose the workflow and sampler bars."""

    _app()
    strip = GenerationProgressStrip()

    assert strip.minimumHeight() == 6
    assert strip.maximumHeight() == 6
    assert strip.workflow_bar.height() == 3
    assert strip.sampler_bar.height() == 3
    assert cast(QLayout, strip.layout()).count() == 2
    assert strip.isHidden() is True


def test_generation_progress_strip_applies_values_and_visibility_gate() -> None:
    """Progress strip should show only when active progress and local gate agree."""

    _app()
    strip = GenerationProgressStrip()

    strip.apply_progress_view(
        ProgressViewState(show_overlay=True, workflow_value=33, sampler_value=44)
    )
    assert strip.workflow_bar.value() == 33
    assert strip.sampler_bar.value() == 44
    assert strip.isHidden() is True

    strip.set_progress_visible(True)
    assert strip.isHidden() is False

    strip.apply_progress_view(
        ProgressViewState(show_overlay=False, workflow_value=100, sampler_value=100)
    )
    assert strip.isHidden() is True


def test_generation_progress_strip_clamps_direct_values() -> None:
    """Direct value updates should stay within progress bar bounds."""

    _app()
    strip = GenerationProgressStrip()

    strip.set_progress_values(125, -5)

    assert strip.workflow_bar.value() == 100
    assert strip.sampler_bar.value() == 0


def test_generation_progress_strip_replay_sets_values_without_animation() -> None:
    """Selection replay should snap qfluent bars to stored values."""

    _app()
    strip = GenerationProgressStrip()

    strip.apply_progress_view(
        ProgressViewState(show_overlay=True, workflow_value=33, sampler_value=44),
        mode=ProgressProjectionMode.SELECTION_REPLAY,
    )

    assert strip.workflow_bar.value() == 33
    assert strip.sampler_bar.value() == 44
    assert strip.workflow_bar.isUseAni() is True
    assert strip.sampler_bar.isUseAni() is True


def _app() -> QApplication:
    """Return the shared QApplication used by progress strip tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)
