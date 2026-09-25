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

"""Mount production editor panels and their minimum shell collaboration surface."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtWidgets import QVBoxLayout, QWidget
from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.localization import (
    ActiveComfyNodeCatalogStore,
    NodePresentationService,
)
from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.domain.workflow.models import WorkflowState
from substitute.presentation.editor.panel.view import EditorPanel

from .fake_gateways import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    FixtureNodeDefinitionGateway,
)
from .trace_events import ProjectionTraceRecorder


@dataclass(slots=True)
class TraceShell:
    """Store the fake shell object and trace-owned callback state."""

    shell: Any
    override_manager: "TraceOverrideManager"
    projection_complete: bool = False
    action_log: list[str] = field(default_factory=list)


def build_editor_panel(
    *,
    host: QWidget,
    workflow_id: str,
    definitions: Mapping[str, Any],
) -> EditorPanel:
    """Create a real editor panel with fixture-backed collaborators."""

    from tests.support.execution.runtime_support import (
        immediate_editor_panel_execution_factories,
    )

    _configure_editor_control_registry()
    gateway = FixtureNodeDefinitionGateway(definitions)
    node_catalog_store = ActiveComfyNodeCatalogStore()
    panel = EditorPanel(
        node_definition_gateway=gateway,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        node_behavior_service=NodeBehaviorService(node_definition_gateway=gateway),
        node_presentation_service=NodePresentationService(
            lambda: node_catalog_store.snapshot("en"),
            application_text_renderer=render_source_application_text,
        ),
        workflow_id=workflow_id,
        editor_panel_execution_factories=(immediate_editor_panel_execution_factories()),
    )
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(cast(QWidget, panel))
    return panel


def build_trace_shell(
    *,
    workflow_id: str,
    workflow: WorkflowState,
    panel: EditorPanel,
    recorder: ProjectionTraceRecorder,
) -> TraceShell:
    """Create the minimum shell surface needed by editor refresh orchestration."""

    trace = TraceShell(
        shell=None,
        override_manager=TraceOverrideManager(recorder=recorder),
    )
    shell = SimpleNamespace(
        _detached_for_gui_reload=False,
        _active_workspace_route=workflow_id,
        _backend_state="ready",
        _current_generate_mode="generate",
        _generation_queue_panel_visible=False,
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows={workflow_id: workflow},
        ),
        get_active_workflow=lambda: workflow,
        active_editor_panel=panel,
        active_override_manager=trace.override_manager,
        editor_panel_container=SimpleNamespace(currentWidget=lambda: panel),
        cube_stack_container=SimpleNamespace(currentWidget=lambda: None),
        workspace_generation_controller=SimpleNamespace(is_continuous_active=False),
        generation_job_queue_service=SimpleNamespace(
            has_active_job=lambda: False,
            has_cancellable_jobs=lambda: False,
            jobs=lambda: (),
        ),
        generationActionCluster=TraceGenerationActionCluster(recorder=recorder),
        refresh_input_canvas_availability=lambda: _record_action(
            trace,
            recorder,
            "refresh_input_canvas_availability",
        ),
        begin_editor_busy=lambda _workflow_id, message: _begin_busy(
            trace,
            recorder,
            _workflow_id,
            message,
        ),
        end_editor_busy=lambda token: _end_busy(trace, recorder, token),
    )
    shell.generation_action_controller = SimpleNamespace(
        apply_generation_action_availability=lambda: _record_action(
            trace,
            recorder,
            "apply_generation_action_availability",
        )
    )
    trace.shell = shell
    return trace


def mark_complete(trace_shell: TraceShell, recorder: ProjectionTraceRecorder) -> None:
    """Mark shell projection completion in the trace."""

    trace_shell.projection_complete = True
    _record_action(trace_shell, recorder, "projection_complete")


class TraceOverrideManager:
    """Record override-manager calls without mutating fixture buffers."""

    def __init__(self, *, recorder: ProjectionTraceRecorder) -> None:
        """Store trace dependencies."""

        self._recorder = recorder
        self._global_override_controls: dict[str, object] = {}

    def sync_state_from_workflow(self) -> None:
        """Record workflow override synchronization."""

        self._recorder.increment("override.sync_state_from_workflow.calls")
        self._recorder.mark("override.sync_state_from_workflow")

    def apply_global_overrides_without_snapshot_fallback(self) -> bool:
        """Record pre-projection override application."""

        self._recorder.increment("override.apply_without_snapshot_fallback.calls")
        self._recorder.mark("override.apply_without_snapshot_fallback")
        return False

    def materialize_default_overrides(self) -> bool:
        """Record default override materialization."""

        self._recorder.increment("override.materialize_default_overrides.calls")
        self._recorder.mark("override.materialize_default_overrides")
        return False

    def apply_global_overrides(
        self,
        *,
        use_cached_behavior_snapshot: bool = True,
    ) -> None:
        """Record final override application."""

        self._recorder.increment("override.apply_global_overrides.calls")
        self._recorder.mark(
            "override.apply_global_overrides",
            use_cached_behavior_snapshot=use_cached_behavior_snapshot,
        )

    def rebuild_override_menu(self) -> None:
        """Record deferred override menu rebuild."""

        self._recorder.increment("override.rebuild_override_menu.calls")
        self._recorder.mark("override.rebuild_override_menu")

    def rebuild_active_override_controls(self) -> None:
        """Record deferred override-control rebuild."""

        self._recorder.increment("override.rebuild_active_override_controls.calls")
        self._recorder.mark("override.rebuild_active_override_controls")


class TraceGenerationActionCluster:
    """Record generation-action presentation calls from shell orchestration."""

    def __init__(self, *, recorder: ProjectionTraceRecorder) -> None:
        """Store trace dependencies."""

        self._recorder = recorder

    def apply_generation_presentation(self, presentation: object) -> None:
        """Record generation action presentation updates."""

        self._recorder.increment("generation.apply_presentation.calls")
        self._recorder.mark(
            "generation.apply_presentation",
            presentation_type=type(presentation).__name__,
        )


def _configure_editor_control_registry() -> None:
    """Configure production control builders for standalone rig execution."""

    from substitute.application.overrides.control_registry_service import (
        configure_control_registry_service,
    )
    from substitute.infrastructure.controls.registry import (
        get_registry,
        register_builtin_control_builders,
    )
    from substitute.presentation.editor.panel.factories.field_pipeline import (
        _register_control_registry_builders,
    )

    def lookup_builder(control: str) -> Callable[..., object] | None:
        """Resolve one registered editor control builder."""

        return cast(Callable[..., object] | None, get_registry().get(control))

    configure_control_registry_service(
        widget_builder_lookup=lookup_builder,
        builtin_control_registrar=register_builtin_control_builders,
    )
    _register_control_registry_builders()


def _record_action(
    trace_shell: TraceShell,
    recorder: ProjectionTraceRecorder,
    action: str,
) -> None:
    """Record a shell-level action in both log and counter form."""

    trace_shell.action_log.append(action)
    recorder.increment(f"shell.{action}.calls")
    recorder.mark(f"shell.{action}")


def _begin_busy(
    trace_shell: TraceShell,
    recorder: ProjectionTraceRecorder,
    workflow_id: str,
    message: str,
) -> str:
    """Record busy-overlay entry and return a token."""

    _record_action(trace_shell, recorder, "begin_editor_busy")
    recorder.mark(
        "shell.begin_editor_busy.details",
        workflow_id=workflow_id,
        message=message,
    )
    return f"busy:{workflow_id}:{message}"


def _end_busy(
    trace_shell: TraceShell,
    recorder: ProjectionTraceRecorder,
    token: object,
) -> None:
    """Record busy-overlay exit."""

    _record_action(trace_shell, recorder, "end_editor_busy")
    recorder.mark("shell.end_editor_busy.details", token=repr(token))
