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

"""Tests for workspace generation action binding helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.application.ports import InterruptResult
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationUiBindings,
)
from substitute.presentation.shell.workspace_generation_action_adapter import (
    handle_generate_clicked,
    handle_interrupt_clicked,
    handle_skip_generation_clicked,
    handle_stop_generation_clicked,
)


from tests.presentation.shell.generation.actions.support import (
    _bindings,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_action_adapter.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
)


def test_handle_generate_clicked_routes_mode_and_bindings_to_controller() -> None:
    """Generate intent should preserve selected mode and built bindings."""

    bindings = _bindings()
    generate_calls: list[tuple[str, GenerationUiBindings]] = []
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow-a"),
        _current_generate_mode="continuous",
        workspace_generation_controller=SimpleNamespace(
            handle_generate_clicked=lambda *, current_mode, bindings: (
                generate_calls.append((current_mode, bindings))
            )
        ),
    )

    handle_generate_clicked(
        view=cast(Any, view),
        build_generation_bindings=lambda: bindings,
    )

    assert generate_calls == [("continuous", bindings)]


def test_handle_interrupt_clicked_clears_progress_after_success() -> None:
    """Interrupt intent should clear model and shell progress after success."""

    interrupt_calls: list[bool] = []
    retire_calls: list[str] = []
    model_progress_clears: list[str] = []
    shell_progress_clears: list[str] = []
    failure_calls: list[InterruptResult] = []

    def _interrupt_generation() -> InterruptResult:
        """Record interrupt invocation and return success."""

        interrupt_calls.append(True)
        return InterruptResult(status="sent", status_code=200, error=None)

    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow-a"),
        generation_feedback_dispatcher=SimpleNamespace(
            retire_progress=lambda *, reason, **_kwargs: retire_calls.append(reason)
        ),
        workspace_generation_controller=SimpleNamespace(
            interrupt_generation=_interrupt_generation
        ),
        editor_panels={
            "workflow-a": SimpleNamespace(
                clear_model_field_load_progress=(
                    lambda: model_progress_clears.append("workflow-a")
                )
            )
        },
        generation_action_controller=SimpleNamespace(
            clear_generation_progress=lambda: shell_progress_clears.append("generation")
        ),
        generation_interrupt_failure_presenter=SimpleNamespace(
            log_interrupt_failure=failure_calls.append
        ),
    )

    handle_interrupt_clicked(view=cast(Any, view))

    assert interrupt_calls == [True]
    assert retire_calls == ["interrupted"]
    assert model_progress_clears == ["workflow-a"]
    assert shell_progress_clears == ["generation"]
    assert failure_calls == []


def test_handle_skip_generation_clicked_clears_progress_when_queue_is_idle() -> None:
    """Skip intent should clear shell progress once no queued job remains active."""

    bindings = _bindings()
    skip_calls: list[GenerationUiBindings] = []
    retire_calls: list[str] = []
    shell_progress_clears: list[str] = []
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow-a"),
        generation_feedback_dispatcher=SimpleNamespace(
            retire_progress=lambda *, reason, **_kwargs: retire_calls.append(reason)
        ),
        workspace_generation_controller=SimpleNamespace(
            skip_active_queue_job=lambda *, bindings: skip_calls.append(bindings)
        ),
        generation_job_queue_service=SimpleNamespace(has_active_job=lambda: False),
        generation_action_controller=SimpleNamespace(
            clear_generation_progress=lambda: shell_progress_clears.append("generation")
        ),
    )

    handle_skip_generation_clicked(
        view=cast(Any, view),
        build_generation_bindings=lambda: bindings,
    )

    assert skip_calls == [bindings]
    assert retire_calls == ["skipped"]
    assert shell_progress_clears == ["generation"]


def test_handle_skip_generation_clicked_keeps_progress_for_active_queue() -> None:
    """Skip intent should keep progress when replacement queue work is active."""

    bindings = _bindings()
    shell_progress_clears: list[str] = []
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow-a"),
        generation_feedback_dispatcher=SimpleNamespace(
            retire_progress=lambda *, reason, **_kwargs: None
        ),
        workspace_generation_controller=SimpleNamespace(
            skip_active_queue_job=lambda *, bindings: None
        ),
        generation_job_queue_service=SimpleNamespace(has_active_job=lambda: True),
        generation_action_controller=SimpleNamespace(
            clear_generation_progress=lambda: shell_progress_clears.append("generation")
        ),
    )

    handle_skip_generation_clicked(
        view=cast(Any, view),
        build_generation_bindings=lambda: bindings,
    )

    assert shell_progress_clears == []


def test_handle_stop_generation_clicked_clears_progress_after_success() -> None:
    """Stop intent should cancel queue work and clear progress after success."""

    bindings = _bindings()
    cancel_calls: list[GenerationUiBindings] = []
    retire_calls: list[str] = []
    model_progress_clears: list[str] = []
    shell_progress_clears: list[str] = []

    def _cancel_generation_queue(*, bindings: GenerationUiBindings) -> None:
        """Record queue cancellation invocation."""

        cancel_calls.append(bindings)

    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow-a"),
        generation_feedback_dispatcher=SimpleNamespace(
            retire_progress=lambda *, reason, **_kwargs: retire_calls.append(reason)
        ),
        workspace_generation_controller=SimpleNamespace(
            cancel_generation_queue=_cancel_generation_queue
        ),
        editor_panels={
            "workflow-a": SimpleNamespace(
                clear_model_field_load_progress=(
                    lambda: model_progress_clears.append("workflow-a")
                )
            )
        },
        generation_action_controller=SimpleNamespace(
            clear_generation_progress=lambda: shell_progress_clears.append("generation")
        ),
    )

    handle_stop_generation_clicked(
        view=cast(Any, view),
        build_generation_bindings=lambda: bindings,
    )

    assert cancel_calls == [bindings]
    assert retire_calls == ["stopped"]
    assert model_progress_clears == ["workflow-a"]
    assert shell_progress_clears == ["generation"]


def test_handle_stop_generation_clicked_reports_failed_interrupt_without_cleanup() -> (
    None
):
    """Stop intent should preserve progress when fallback interrupt fails."""

    failed_result = InterruptResult(status="failed", status_code=500, error="boom")
    bindings = _bindings()
    failure_calls: list[InterruptResult] = []
    retire_calls: list[str] = []
    shell_progress_clears: list[str] = []
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow-a"),
        generation_feedback_dispatcher=SimpleNamespace(
            retire_progress=lambda *, reason, **_kwargs: retire_calls.append(reason)
        ),
        workspace_generation_controller=SimpleNamespace(
            cancel_generation_queue=lambda *, bindings: failed_result
        ),
        generation_action_controller=SimpleNamespace(
            clear_generation_progress=lambda: shell_progress_clears.append("generation")
        ),
        generation_interrupt_failure_presenter=SimpleNamespace(
            log_interrupt_failure=failure_calls.append
        ),
    )

    handle_stop_generation_clicked(
        view=cast(Any, view),
        build_generation_bindings=lambda: bindings,
    )

    assert failure_calls == [failed_result]
    assert retire_calls == []
    assert shell_progress_clears == []
