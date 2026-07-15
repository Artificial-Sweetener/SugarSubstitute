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

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.application.generation import (
    GenerationRequest,
    SeedRandomizationResult,
    SeedRandomizationService,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.ports import InterruptResult
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationUiBindings,
)
from substitute.presentation.shell.workspace_generation_action_adapter import (
    GenerationActionBindingView,
    build_generation_action_bindings,
    effective_generation_batch_count,
    handle_generate_clicked,
    handle_interrupt_clicked,
    handle_skip_generation_clicked,
    handle_stop_generation_clicked,
    randomize_generation_request_seeds,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
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


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _dispatcher() -> SimpleNamespace:
    """Return distinct generation feedback callbacks."""

    return SimpleNamespace(
        on_run_started=lambda _event: None,
        on_progress=lambda _progress: None,
        on_model_load_progress=lambda _progress: None,
        on_preview=lambda _preview: None,
        on_output_image=lambda _output: None,
        on_failure=lambda _failure: None,
        on_timing=lambda _timing: None,
        on_completed=lambda _event: None,
    )


def _bindings() -> GenerationUiBindings:
    """Return inert generation bindings for action-intent tests."""

    return GenerationUiBindings(
        build_generation_request=lambda: cast(Any, None),
        randomize_seeds=lambda: None,
        clear_output_for_workflow=lambda _workflow_id: None,
        on_progress=lambda _progress: None,
        on_model_load_progress=lambda _progress: None,
        on_preview=lambda _preview: None,
        on_output_image=lambda _output: None,
        on_failure=lambda _failure: None,
        on_timing=lambda _timing: None,
        on_completed=lambda _event: None,
        refresh_generation_actions=lambda: None,
    )


def test_build_generation_action_bindings_routes_feedback_and_randomizes_request() -> (
    None
):
    """Generation bindings should route feedback and randomize before returning."""

    dispatcher = _dispatcher()
    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )
    request = GenerationRequest(
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        workflow=cast(Any, SimpleNamespace()),
    )
    randomizer_calls: list[tuple[GenerationRequest, EditorBehaviorSnapshot | None]] = []

    view = SimpleNamespace(
        generation_feedback_dispatcher=dispatcher,
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: None
        ),
        editor_panels={
            "workflow-a": SimpleNamespace(
                current_behavior_snapshot=lambda: behavior_snapshot
            )
        },
    )

    def _randomize(
        *,
        request: GenerationRequest,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> SeedRandomizationResult:
        """Record seed randomization inputs."""

        randomizer_calls.append((request, behavior_snapshot))
        return SeedRandomizationResult()

    bindings = cast(
        Any,
        build_generation_action_bindings(
            view=cast(GenerationActionBindingView, view),
            build_generation_request=lambda: request,
            randomize_generation_request_seeds=_randomize,
            build_queued_generation_snapshots=lambda: (),
            capture_queued_generation_preparation=lambda: object(),
        ),
    )

    assert bindings.build_generation_request() is request
    assert randomizer_calls == [(request, behavior_snapshot)]
    assert bindings.on_run_started is dispatcher.on_run_started
    assert bindings.on_progress is dispatcher.on_progress
    assert bindings.on_model_load_progress is dispatcher.on_model_load_progress
    assert bindings.on_preview is dispatcher.on_preview
    assert bindings.on_output_image is dispatcher.on_output_image
    assert bindings.on_failure is dispatcher.on_failure
    assert bindings.on_timing is dispatcher.on_timing
    assert bindings.on_completed is dispatcher.on_completed
    assert bindings.build_queued_generation_snapshots() == ()


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


def test_effective_generation_batch_count_prefers_registry_and_clamps() -> None:
    """Titlebar registry batch count should win over legacy cluster values."""

    view = SimpleNamespace(
        generation_titlebar_control_registry=SimpleNamespace(
            effective_batch_count=lambda: 0
        ),
        generationActionCluster=SimpleNamespace(effective_batch_count=lambda: 7),
    )

    assert effective_generation_batch_count(view) == 1


def test_effective_generation_batch_count_uses_legacy_cluster_fallback() -> None:
    """Legacy generation action cluster should supply batch count when needed."""

    view = SimpleNamespace(
        generationActionCluster=SimpleNamespace(effective_batch_count=lambda: 4)
    )

    assert effective_generation_batch_count(view) == 4
    assert effective_generation_batch_count(SimpleNamespace()) == 1


def test_randomize_generation_request_seeds_delegates_to_service() -> None:
    """Seed randomization should delegate workflow mutation to the service port."""

    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )
    workflow = SimpleNamespace()
    request = GenerationRequest(
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        workflow=cast(Any, workflow),
    )
    calls: list[tuple[object, EditorBehaviorSnapshot | None]] = []

    class _SeedRandomizer:
        """Record seed randomization calls."""

        def randomize_workflow_seeds(
            self,
            *,
            workflow: object,
            behavior_snapshot: EditorBehaviorSnapshot | None,
        ) -> SeedRandomizationResult:
            """Record request workflow and behavior snapshot."""

            calls.append((workflow, behavior_snapshot))
            return SeedRandomizationResult()

    randomize_generation_request_seeds(
        seed_randomization_service=_SeedRandomizer(),
        request=request,
        behavior_snapshot=behavior_snapshot,
    )

    assert calls == [(workflow, behavior_snapshot)]


def test_randomize_generation_request_seeds_skips_plain_workflow_for_concrete_service() -> (
    None
):
    """Concrete seed randomizer should ignore plain non-WorkflowState requests."""

    request = GenerationRequest(
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        workflow=cast(Any, SimpleNamespace()),
    )

    randomize_generation_request_seeds(
        seed_randomization_service=SeedRandomizationService(),
        request=request,
        behavior_snapshot=None,
    )


def test_workspace_generation_action_adapter_imports_no_qt_boundaries() -> None:
    """Generation action binding helpers should not import Qt or controller facade."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(SOURCE_PATH)
            if imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()
