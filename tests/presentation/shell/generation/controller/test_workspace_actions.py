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

from substitute.application.ports import (
    InterruptResult,
)
from substitute.presentation.shell.workspace_generation_action_adapter import (
    WorkspaceGenerationActions,
)


def test_workspace_skip_click_skips_active_queue_job() -> None:
    """Workspace skip intent should route to the generation controller."""

    bindings = object()
    skip_calls: list[object | None] = []
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
            "workspace_generation_controller": type(
                "Controller",
                (),
                {
                    "skip_active_queue_job": lambda self, *, bindings: (
                        skip_calls.append(bindings)
                    )
                },
            )(),
            "generation_job_queue_service": type(
                "Queue",
                (),
                {"has_active_job": lambda self: False},
            )(),
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
    ).on_skip_generation_clicked()

    assert skip_calls == [bindings]
    assert retire_calls == ["skipped"]
    assert progress_clear_calls == [True]


def test_workspace_skip_click_keeps_generation_progress_when_queue_has_active_job() -> (
    None
):
    """Workspace skip should keep progress while replacement queue work is active."""

    bindings = object()
    skip_calls: list[object | None] = []
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
            "workspace_generation_controller": type(
                "Controller",
                (),
                {
                    "skip_active_queue_job": lambda self, *, bindings: (
                        skip_calls.append(bindings)
                    )
                },
            )(),
            "generation_job_queue_service": type(
                "Queue",
                (),
                {"has_active_job": lambda self: True},
            )(),
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
    ).on_skip_generation_clicked()

    assert skip_calls == [bindings]
    assert retire_calls == ["skipped"]
    assert progress_clear_calls == []


def test_workspace_interrupt_click_clears_generation_progress_after_success() -> None:
    """Workspace interrupt should clear progress after a successful interrupt."""

    clear_calls: list[str] = []
    interrupt_calls: list[bool] = []
    retire_calls: list[str] = []

    def interrupt_generation(_self: object) -> InterruptResult:
        """Record interruption and return a successful result."""

        interrupt_calls.append(True)
        return InterruptResult(status="sent", status_code=200, error=None)

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
                    "interrupt_generation": interrupt_generation,
                },
            )(),
            "editor_panels": {
                "wf": type(
                    "Panel",
                    (),
                    {
                        "clear_model_field_load_progress": lambda self: (
                            clear_calls.append("model_fields")
                        )
                    },
                )()
            },
            "generation_action_controller": type(
                "GenerationActionController",
                (),
                {
                    "clear_generation_progress": lambda self: clear_calls.append(
                        "generation_progress"
                    )
                },
            )(),
        },
    )()
    WorkspaceGenerationActions(
        cast(Any, view),
        build_generation_bindings=lambda: cast(Any, None),
    ).on_interrupt_clicked()

    assert interrupt_calls == [True]
    assert retire_calls == ["interrupted"]
    assert clear_calls == ["model_fields", "generation_progress"]
