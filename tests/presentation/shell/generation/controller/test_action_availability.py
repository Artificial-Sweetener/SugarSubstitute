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

"""Cover generation action-availability projection."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
)
from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
)


class _GenerationActionCluster:
    """Capture generation action presentation updates."""

    def __init__(self) -> None:
        """Initialize the captured presentation collection."""

        self.presentation_updates: list[GenerationActionPresentation] = []

    def apply_generation_presentation(
        self,
        presentation: GenerationActionPresentation,
    ) -> None:
        """Record one complete generation action presentation snapshot."""

        self.presentation_updates.append(presentation)


def test_detached_shell_ignores_stale_generation_availability_callbacks() -> None:
    """Old shells should not touch deleted titlebar controls after GUI reload."""

    calls: list[str] = []
    shell = SimpleNamespace(
        _detached_for_gui_reload=True,
        generationActionCluster=SimpleNamespace(
            apply_generation_presentation=lambda _presentation: calls.append(
                "availability"
            )
        ),
    )

    GenerationActionController(shell).apply_generation_action_availability()

    assert calls == []


def test_generation_action_availability_fans_out_through_registry() -> None:
    """Registry should receive shell generation presentation when attached."""

    registry_presentations: list[GenerationActionPresentation] = []
    cluster = _GenerationActionCluster()
    shell = SimpleNamespace(
        _detached_for_gui_reload=False,
        generationActionCluster=cluster,
        generation_titlebar_control_registry=SimpleNamespace(
            apply_generation_presentation=registry_presentations.append
        ),
        _backend_state="ready",
        _current_generate_mode="generate",
        _active_workspace_route="wf-a",
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": SimpleNamespace(cubes={"Cube": object()})},
        ),
        workspace_generation_controller=SimpleNamespace(is_continuous_active=False),
        generation_job_queue_service=SimpleNamespace(
            has_active_job=lambda: False,
            has_cancellable_jobs=lambda: False,
            jobs=lambda: (),
        ),
        generation_queue_controller=SimpleNamespace(panel_visible=False),
    )

    GenerationActionController(shell).apply_generation_action_availability()

    assert len(registry_presentations) == 1
    assert registry_presentations[0].play_enabled is True
    assert cluster.presentation_updates == []
