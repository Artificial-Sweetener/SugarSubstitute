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

"""Contract tests for workspace generation presentation controller behavior."""

from __future__ import annotations

from typing import Any, cast

from substitute.application.generation import (
    GenerationService,
)
from substitute.application.ports import (
    InterruptResult,
)
from substitute.presentation.shell.generation_action_projection import (
    project_generation_actions,
)
from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
    GenerationActionState,
)
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationUiBindings,
    WorkspaceGenerationController,
)
from substitute.presentation.shell.workspace_generation_action_adapter import (
    WorkspaceGenerationActions,
)


from tests.presentation.shell.generation.controller.support import (
    _FakeGenerationService,
    _FakeGenerationQueueService,
    _BindingRecorder,
    _snapshot,
    _bindings_with_snapshots,
)


def test_workspace_stop_click_cancels_generation_queue() -> None:
    """Workspace stop intent should request queue-wide cancellation and clear progress."""

    clear_calls: list[bool] = []
    progress_clear_calls: list[bool] = []
    cancel_calls: list[object | None] = []
    retire_calls: list[str] = []
    bindings = object()

    def cancel_generation_queue(_self: object, *, bindings: object) -> None:
        """Record the bindings supplied to queue cancellation."""

        cancel_calls.append(bindings)

    view = type(
        "View",
        (),
        {
            "generation_feedback_dispatcher": type(
                "FeedbackDispatcher",
                (),
                {
                    "retire_progress": lambda self, *, reason, **_kwargs: (
                        retire_calls.append(reason)
                    )
                },
            )(),
            "workspace_generation_controller": type(
                "Controller",
                (),
                {
                    "cancel_generation_queue": cancel_generation_queue,
                },
            )(),
            "editor_panels": {
                "wf": type(
                    "Panel",
                    (),
                    {
                        "clear_model_field_load_progress": lambda self: (
                            clear_calls.append(True)
                        )
                    },
                )()
            },
            "generation_action_controller": type(
                "GenerationActionController",
                (),
                {
                    "clear_generation_progress": lambda self: (
                        progress_clear_calls.append(True)
                    )
                },
            )(),
        },
    )()
    WorkspaceGenerationActions(
        cast(Any, view),
        build_generation_bindings=lambda: cast(Any, bindings),
    ).on_stop_generation_clicked()

    assert cancel_calls == [bindings]
    assert retire_calls == ["stopped"]
    assert clear_calls == [True]
    assert progress_clear_calls == [True]


def test_workspace_stop_click_reprojects_active_continuous_as_inactive() -> None:
    """Stop-all should restore continuous visuals through state projection."""

    fake_service = _FakeGenerationService()
    fake_queue = _FakeGenerationQueueService()
    controller = WorkspaceGenerationController(
        cast(GenerationService, fake_service),
        cast(Any, fake_queue),
    )
    presentations: list[GenerationActionPresentation] = []

    def _record_projection() -> None:
        presentations.append(
            project_generation_actions(
                GenerationActionState(
                    selected_mode="continuous",
                    continuous_active=controller.is_continuous_active,
                    backend_ready=True,
                    workflow_runnable=True,
                    settings_route_active=False,
                    queue_has_active=fake_queue.has_active_job(),
                    queue_has_cancellable=fake_queue.has_cancellable_jobs(),
                    pending_queue_count=0,
                    queue_has_visible_jobs=False,
                    queue_panel_visible=False,
                )
            )
        )

    recorder = _BindingRecorder([], [], [], [], [], [])
    base_bindings = _bindings_with_snapshots(recorder, (_snapshot(),))
    bindings = GenerationUiBindings(
        build_generation_request=base_bindings.build_generation_request,
        randomize_seeds=base_bindings.randomize_seeds,
        on_progress=base_bindings.on_progress,
        on_model_load_progress=base_bindings.on_model_load_progress,
        on_preview=base_bindings.on_preview,
        on_output_image=base_bindings.on_output_image,
        on_failure=base_bindings.on_failure,
        on_timing=base_bindings.on_timing,
        on_completed=base_bindings.on_completed,
        refresh_generation_actions=_record_projection,
        build_queued_generation_snapshots=base_bindings.build_queued_generation_snapshots,
    )
    clear_calls: list[bool] = []
    progress_clear_calls: list[bool] = []
    retire_calls: list[str] = []
    view = type(
        "View",
        (),
        {
            "generation_feedback_dispatcher": type(
                "FeedbackDispatcher",
                (),
                {
                    "retire_progress": lambda self, *, reason, **_kwargs: (
                        retire_calls.append(reason)
                    )
                },
            )(),
            "workspace_generation_controller": controller,
            "editor_panels": {
                "wf": type(
                    "Panel",
                    (),
                    {
                        "clear_model_field_load_progress": lambda self: (
                            clear_calls.append(True)
                        )
                    },
                )()
            },
            "generation_action_controller": type(
                "GenerationActionController",
                (),
                {
                    "clear_generation_progress": lambda self: (
                        progress_clear_calls.append(True)
                    )
                },
            )(),
        },
    )()
    controller.handle_generate_clicked(current_mode="continuous", bindings=bindings)
    assert presentations[-1].play_mode == "end_continuous"

    WorkspaceGenerationActions(
        cast(Any, view),
        build_generation_bindings=lambda: bindings,
    ).on_stop_generation_clicked()

    assert controller.is_continuous_active is False
    assert fake_queue.cancel_all_calls == 1
    final_play_mode: str = presentations[-1].play_mode
    assert final_play_mode == "continuous"
    assert retire_calls == ["stopped"]
    assert clear_calls == [True]
    assert progress_clear_calls == [True]


def test_workspace_stop_click_does_not_clear_generation_progress_after_failed_interrupt() -> (
    None
):
    """Workspace stop should leave progress alone when fallback interrupt fails."""

    clear_calls: list[bool] = []
    progress_clear_calls: list[bool] = []
    failure_calls: list[InterruptResult] = []
    retire_calls: list[str] = []
    failed_result = InterruptResult(
        status="failed",
        status_code=500,
        error="boom",
    )
    bindings = object()
    view = type(
        "View",
        (),
        {
            "generation_feedback_dispatcher": type(
                "FeedbackDispatcher",
                (),
                {
                    "retire_progress": lambda self, *, reason, **_kwargs: (
                        retire_calls.append(reason)
                    )
                },
            )(),
            "workspace_generation_controller": type(
                "Controller",
                (),
                {"cancel_generation_queue": lambda self, *, bindings: failed_result},
            )(),
            "editor_panels": {
                "wf": type(
                    "Panel",
                    (),
                    {
                        "clear_model_field_load_progress": lambda self: (
                            clear_calls.append(True)
                        )
                    },
                )()
            },
            "generation_action_controller": type(
                "GenerationActionController",
                (),
                {
                    "clear_generation_progress": lambda self: (
                        progress_clear_calls.append(True)
                    )
                },
            )(),
            "generation_interrupt_failure_presenter": type(
                "FailurePresenter",
                (),
                {
                    "log_interrupt_failure": lambda self, result: failure_calls.append(
                        result
                    )
                },
            )(),
        },
    )()
    WorkspaceGenerationActions(
        cast(Any, view),
        build_generation_bindings=lambda: cast(Any, bindings),
    ).on_stop_generation_clicked()

    assert failure_calls == [failed_result]
    assert retire_calls == []
    assert clear_calls == []
    assert progress_clear_calls == []
