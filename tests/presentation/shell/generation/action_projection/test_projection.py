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

"""Contract tests for generation titlebar state projection."""

from __future__ import annotations

from substitute.presentation.shell.generation_action_projection import (
    project_generation_actions,
)
from substitute.presentation.shell.generation_action_state import (
    GenerationActionState,
    GenerationSelectedMode,
)


def test_projection_enables_generate_for_ready_runnable_workflow() -> None:
    """Ready runnable generate mode should expose normal generation controls."""

    presentation = project_generation_actions(_state())

    assert presentation.play_mode == "generate"
    assert presentation.play_enabled is True
    assert presentation.play_tooltip == "Generate"
    assert presentation.batch_accessory_visible is True
    assert presentation.batch_accessory_enabled is True
    assert presentation.stop_enabled is False
    assert presentation.skip_enabled is False
    assert presentation.mode_menu_enabled is True


def test_projection_disables_normal_start_when_backend_is_not_ready() -> None:
    """Backend unavailability should block normal starts without hiding stop."""

    presentation = project_generation_actions(
        _state(backend_ready=False, queue_has_cancellable=True)
    )

    assert presentation.play_mode == "generate"
    assert presentation.play_enabled is False
    assert presentation.batch_accessory_visible is True
    assert presentation.batch_accessory_enabled is False
    assert presentation.mode_menu_enabled is False
    assert presentation.stop_enabled is True


def test_projection_shows_continuous_when_selected_and_inactive() -> None:
    """Inactive continuous mode should show infinity and hide batch controls."""

    presentation = project_generation_actions(_state(selected_mode="continuous"))

    assert presentation.play_mode == "continuous"
    assert presentation.play_enabled is True
    assert presentation.play_tooltip == "Continuous"
    assert presentation.batch_accessory_visible is False
    assert presentation.batch_accessory_enabled is False
    assert presentation.mode_menu_enabled is True


def test_projection_shows_end_continuous_while_loop_is_active() -> None:
    """Active continuous state should expose end-loop, stop, and skip actions."""

    presentation = project_generation_actions(
        _state(
            selected_mode="continuous",
            continuous_active=True,
            backend_ready=False,
            workflow_runnable=False,
            settings_route_active=True,
        )
    )

    assert presentation.play_mode == "end_continuous"
    assert presentation.play_enabled is True
    assert presentation.play_tooltip == "Stop continuous after current job"
    assert presentation.stop_enabled is True
    assert presentation.skip_enabled is True
    assert presentation.batch_accessory_visible is False
    assert presentation.batch_accessory_enabled is False
    assert presentation.mode_menu_enabled is False


def test_projection_enables_skip_for_active_queue_with_pending_followup() -> None:
    """Normal queue skip should require active work plus pending follow-up jobs."""

    presentation = project_generation_actions(
        _state(
            queue_has_active=True,
            queue_has_cancellable=True,
            pending_queue_count=1,
            queue_has_visible_jobs=True,
        )
    )

    assert presentation.skip_enabled is True
    assert presentation.stop_enabled is True
    assert presentation.queue_primary_enabled is True
    assert presentation.queue_badge_count == 1


def test_projection_disables_normal_skip_without_pending_followup() -> None:
    """Active normal queue work without pending jobs should leave skip disabled."""

    presentation = project_generation_actions(
        _state(
            queue_has_active=True,
            queue_has_cancellable=True,
            pending_queue_count=0,
            queue_has_visible_jobs=True,
        )
    )

    assert presentation.skip_enabled is False
    assert presentation.stop_enabled is True
    assert presentation.queue_primary_enabled is True
    assert presentation.queue_badge_count == 0


def test_projection_hides_queue_segment_when_full_panel_is_visible() -> None:
    """Visible full queue panel should remove the redundant titlebar segment."""

    presentation = project_generation_actions(
        _state(queue_has_visible_jobs=True, queue_panel_visible=True)
    )

    assert presentation.queue_primary_enabled is True
    assert presentation.queue_segment_visible is False


def test_projection_keeps_queue_primary_enabled_for_visible_terminal_jobs() -> None:
    """Visible queue history should open with no badge when no jobs are pending."""

    presentation = project_generation_actions(
        _state(queue_has_visible_jobs=True, pending_queue_count=-3)
    )

    assert presentation.queue_primary_enabled is True
    assert presentation.queue_badge_count == 0
    assert presentation.queue_segment_visible is True


def _state(
    *,
    selected_mode: GenerationSelectedMode = "generate",
    continuous_active: bool = False,
    backend_ready: bool = True,
    workflow_runnable: bool = True,
    settings_route_active: bool = False,
    queue_has_active: bool = False,
    queue_has_cancellable: bool = False,
    pending_queue_count: int = 0,
    queue_has_visible_jobs: bool = False,
    queue_panel_visible: bool = False,
) -> GenerationActionState:
    """Return a ready runnable default generation action state."""

    return GenerationActionState(
        selected_mode=selected_mode,
        continuous_active=continuous_active,
        backend_ready=backend_ready,
        workflow_runnable=workflow_runnable,
        settings_route_active=settings_route_active,
        queue_has_active=queue_has_active,
        queue_has_cancellable=queue_has_cancellable,
        pending_queue_count=pending_queue_count,
        queue_has_visible_jobs=queue_has_visible_jobs,
        queue_panel_visible=queue_panel_visible,
    )
