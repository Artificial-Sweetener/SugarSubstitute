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

"""Contract tests for generation progress presentation state."""

from __future__ import annotations

from substitute.application.generation.progress_service import ProgressService


def test_build_view_state_clamps_progress_values() -> None:
    """Progress presentation values should stay within 0-100."""
    progress_view = ProgressService().build_view_state(
        active=True,
        workflow_percent=125.4,
        sampler_percent=-7.8,
    )

    assert progress_view.workflow_value == 100
    assert progress_view.sampler_value == 0
    assert progress_view.show_overlay is True


def test_build_view_state_hides_overlay_when_clamped_complete() -> None:
    """Over-complete raw values should not keep the progress overlay visible."""
    progress_view = ProgressService().build_view_state(
        active=True,
        workflow_percent=101.0,
        sampler_percent=100.0,
    )

    assert progress_view.workflow_value == 100
    assert progress_view.sampler_value == 100
    assert progress_view.show_overlay is False
    assert progress_view.active is False


def test_build_view_state_hides_overlay_when_lifecycle_is_inactive() -> None:
    """Inactive lifecycle state should hide progress regardless of stale values."""

    progress_view = ProgressService().build_view_state(
        active=False,
        workflow_percent=43.0,
        sampler_percent=12.0,
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )

    assert progress_view == progress_view.hidden(
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )


def test_build_model_load_view_state_requires_measured_running_percent() -> None:
    """Model-loading overlay should show only measured active progress."""
    service = ProgressService()

    running = service.build_model_load_view_state(percent=37.8, state="running")
    prepared = service.build_model_load_view_state(percent=100.0, state="running")
    missing = service.build_model_load_view_state(percent=None, state="running")
    finished = service.build_model_load_view_state(percent=100.0, state="finished")

    assert running.show_overlay is True
    assert running.value == 37
    assert running.display_percent == 37.8
    assert prepared.show_overlay is True
    assert prepared.value == 99
    assert prepared.display_percent == 99.0
    assert missing.show_overlay is False
    assert missing.value == 0
    assert missing.display_percent is None
    assert finished.show_overlay is False
    assert finished.value == 0
    assert finished.display_percent is None
