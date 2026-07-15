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

"""Run production-path editor projection traces against captured workflow fixtures."""

from __future__ import annotations

import copy
import inspect
import math
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, cast

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from substitute.application.node_behavior.behavior_service import (
    NodeBehaviorRuntimeState,
    NodeBehaviorService,
)
from substitute.domain.common import GlobalOverrideMap
from substitute.domain.cubes import (
    SubgraphWrapperDefinitionIndex,
    materialize_cube_runtime_graph,
    validate_canonical_cube_document,
)
from substitute.domain.workflow.models import CubeState, WorkflowState
from substitute.presentation.editor.panel.widgets import field_row as field_row_view
from substitute.presentation.editor.panel.widgets import node_card as node_card_view
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.editor.panel.cube_section_build_session import (
    CubeSectionBuildSession,
)
from substitute.presentation.editor.panel.projection_coordinator import (
    EditorPanelProjectionCoordinator,
)
from substitute.presentation.editor.panel.node_card_builder import NodeCardBuilder
from substitute.presentation.shell.workflow_surface_reconciler import (
    ActiveWorkflowSurfaceRefresher,
)

from .fake_gateways import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    FixtureNodeDefinitionGateway,
)
from .fixtures import read_json, stable_json_hash, workflow_fixture_path, write_json
from .qt_harness import create_hidden_host, ensure_qapplication
from .scenarios import WorkflowScenario
from .signatures import (
    CubeSectionSignature,
    EditorSettledSignature,
    FieldSignature,
    NodeCardSignature,
)
from .trace_events import ProjectionTraceRecorder


@dataclass(slots=True)
class _TraceShell:
    """Store the fake shell object and trace-owned callback state."""

    shell: Any
    override_manager: "_TraceOverrideManager"
    projection_complete: bool = False
    action_log: list[str] = field(default_factory=list)


def trace_production_scenarios(
    scenarios: Sequence[WorkflowScenario],
    *,
    fixtures_dir: Path,
    iterations: int,
    report_path: Path,
    settle_turns: int = 500,
    write_production_targets: bool = False,
    alternating: bool = False,
) -> dict[str, Any]:
    """Trace real offscreen editor projection for each selected scenario."""

    ensure_qapplication()
    if alternating:
        iteration_reports = _trace_alternating_scenarios(
            scenarios,
            fixtures_dir=fixtures_dir,
            iterations=iterations,
            settle_turns=settle_turns,
        )
    else:
        iteration_reports = []
        for iteration in range(1, iterations + 1):
            for scenario in scenarios:
                iteration_reports.append(
                    _trace_one_scenario(
                        scenario,
                        fixtures_dir=fixtures_dir,
                        iteration=iteration,
                        settle_turns=settle_turns,
                        write_production_target=write_production_targets,
                    )
                )
    report = {
        "schema_version": 1,
        "mode": "production_trace_alternating" if alternating else "production_trace",
        "iterations": iterations,
        "scenario_ids": [scenario.workflow_id for scenario in scenarios],
        "iteration_reports": iteration_reports,
        "aggregates": _aggregate_summary(iteration_reports),
        "budgets": _budget_summary(iteration_reports),
    }
    write_json(report_path, report)
    return report


def _trace_alternating_scenarios(
    scenarios: Sequence[WorkflowScenario],
    *,
    fixtures_dir: Path,
    iterations: int,
    settle_turns: int,
) -> list[dict[str, Any]]:
    """Trace repeated workflow activation while keeping editor panels alive."""

    fixtures: dict[str, Mapping[str, Any]] = {}
    workflows: dict[str, WorkflowState] = {}
    definitions_by_workflow: dict[str, dict[str, Any]] = {}
    panels: dict[str, EditorPanel] = {}
    hosts: list[QWidget] = []
    try:
        for scenario in scenarios:
            fixture = read_json(
                workflow_fixture_path(fixtures_dir, scenario.workflow_id)
            )
            workflow, definitions = _workflow_from_fixture(fixture)
            host = create_hidden_host(show_window=False)
            panel = _build_editor_panel(
                host=host,
                workflow_id=scenario.workflow_id,
                definitions=definitions,
            )
            fixtures[scenario.workflow_id] = fixture
            workflows[scenario.workflow_id] = workflow
            definitions_by_workflow[scenario.workflow_id] = definitions
            panels[scenario.workflow_id] = panel
            hosts.append(host)

        reports: list[dict[str, Any]] = []
        activation = 0
        for iteration in range(1, iterations + 1):
            for scenario in scenarios:
                activation += 1
                reports.append(
                    _trace_existing_panel_activation(
                        scenario,
                        fixture=fixtures[scenario.workflow_id],
                        workflow=workflows[scenario.workflow_id],
                        panel=panels[scenario.workflow_id],
                        all_workflows=workflows,
                        iteration=iteration,
                        activation=activation,
                        settle_turns=settle_turns,
                    )
                )
        return reports
    finally:
        for host in hosts:
            host.close()
            host.deleteLater()
        _drain_qt_events(25)


def _trace_existing_panel_activation(
    scenario: WorkflowScenario,
    *,
    fixture: Mapping[str, Any],
    workflow: WorkflowState,
    panel: EditorPanel,
    all_workflows: Mapping[str, WorkflowState],
    iteration: int,
    activation: int,
    settle_turns: int,
) -> dict[str, Any]:
    """Trace one activation against a panel that may already be clean."""

    expected_signature = fixture.get("production_settled_signature")
    if not isinstance(expected_signature, dict):
        expected_signature = fixture.get("settled_signature")
    expected_hash = (
        stable_json_hash(expected_signature)
        if isinstance(expected_signature, dict)
        else ""
    )
    recorder = ProjectionTraceRecorder()
    trace_shell = _build_trace_shell(
        workflow_id=scenario.workflow_id,
        workflow=workflow,
        panel=panel,
        recorder=recorder,
    )
    trace_shell.shell.workflow_session_service.workflows = dict(all_workflows)
    panel.mainwindow = trace_shell.shell
    projection_signature = panel.current_projection_signature(
        workflow_id=scenario.workflow_id,
        cube_entries=[(alias, workflow.cubes[alias]) for alias in workflow.stack_order],
        cube_states=workflow.cubes,
        stack_order=workflow.stack_order,
    )
    clean_before = panel.is_projection_clean(projection_signature)
    projection_coordinator = getattr(panel, "_projection_coordinator", None)
    invalidation_reason = getattr(
        getattr(projection_coordinator, "_projection_state", None),
        "invalidation_reason",
        "",
    )
    before_widgets = _widget_count()
    recorder.mark(
        "production_trace.activation_start",
        activation=activation,
        widget_count=before_widgets,
        clean_before=clean_before,
        invalidation_reason=str(invalidation_reason),
    )
    with (
        _instrument_projection(recorder),
        recorder.timed(
            "production.total_elapsed_ms",
            workflow_id=scenario.workflow_id,
            activation=activation,
        ),
    ):
        ActiveWorkflowSurfaceRefresher(
            trace_shell.shell
        ).refresh_active_workflow_surface(
            on_complete=lambda: _mark_complete(trace_shell, recorder),
        )
        _drain_until_complete(trace_shell, max_turns=settle_turns)
    _drain_qt_events(10)
    actual_signature = _signature_from_panel(
        workflow_id=scenario.workflow_id,
        workflow=workflow,
        panel=panel,
    ).to_json()
    partial_orphan_field_cards = _partial_orphan_field_card_refs(actual_signature)
    parent_violations = _parent_chain_violations(panel)
    recorder.increment("parenting.violations", len(parent_violations))
    after_widgets = _widget_count()
    recorder.mark(
        "production_trace.activation_end",
        activation=activation,
        widget_count=after_widgets,
        widget_delta=after_widgets - before_widgets,
        projection_complete=trace_shell.projection_complete,
    )
    signature_matched = expected_signature == actual_signature
    mismatches = [] if signature_matched else ["settled_signature"]
    if partial_orphan_field_cards:
        mismatches.append("partial_orphan_field_cards")
    return {
        "scenario_id": scenario.workflow_id,
        "iteration": iteration,
        "activation": activation,
        "projection_completed": trace_shell.projection_complete,
        "signature_matched": signature_matched,
        "signature_hash": stable_json_hash(actual_signature),
        "expected_signature_hash": expected_hash,
        "actual_signature": actual_signature,
        "partial_orphan_field_cards": partial_orphan_field_cards,
        "parent_chain_violations": parent_violations,
        "override_action_log": list(trace_shell.action_log),
        "widget_count_before": before_widgets,
        "widget_count_after": after_widgets,
        "clean_before": clean_before,
        "invalidation_reason_before": str(invalidation_reason),
        "counters": recorder.counters,
        "timings_ms": recorder.timings_ms,
        "events": [event.to_json() for event in recorder.events],
        "mismatches": mismatches,
    }


def _trace_one_scenario(
    scenario: WorkflowScenario,
    *,
    fixtures_dir: Path,
    iteration: int,
    settle_turns: int,
    write_production_target: bool,
) -> dict[str, Any]:
    """Run one fixture through the real shell-to-editor projection path."""

    fixture = read_json(workflow_fixture_path(fixtures_dir, scenario.workflow_id))
    expected_signature = fixture.get("production_settled_signature")
    if not isinstance(expected_signature, dict):
        expected_signature = fixture.get("settled_signature")
    expected_hash = (
        stable_json_hash(expected_signature)
        if isinstance(expected_signature, dict)
        else ""
    )
    workflow, definitions = _workflow_from_fixture(fixture)
    recorder = ProjectionTraceRecorder()
    host = create_hidden_host(show_window=False)
    panel = _build_editor_panel(
        host=host,
        workflow_id=scenario.workflow_id,
        definitions=definitions,
    )
    trace_shell = _build_trace_shell(
        workflow_id=scenario.workflow_id,
        workflow=workflow,
        panel=panel,
        recorder=recorder,
    )
    panel.mainwindow = trace_shell.shell
    before_widgets = _widget_count()
    recorder.mark("production_trace.start", widget_count=before_widgets)
    try:
        with (
            _instrument_projection(recorder),
            recorder.timed(
                "production.total_elapsed_ms",
                workflow_id=scenario.workflow_id,
            ),
        ):
            ActiveWorkflowSurfaceRefresher(
                trace_shell.shell
            ).refresh_active_workflow_surface(
                on_complete=lambda: _mark_complete(trace_shell, recorder),
            )
            _drain_until_complete(trace_shell, max_turns=settle_turns)
        _drain_qt_events(10)
        actual_signature = _signature_from_panel(
            workflow_id=scenario.workflow_id,
            workflow=workflow,
            panel=panel,
        ).to_json()
        partial_orphan_field_cards = _partial_orphan_field_card_refs(actual_signature)
        if write_production_target and partial_orphan_field_cards:
            message = (
                "Refusing to write production settled target with partial orphan "
                f"field cards: {partial_orphan_field_cards!r}"
            )
            raise ValueError(message)
        if write_production_target:
            _write_production_target(
                fixture_path=workflow_fixture_path(fixtures_dir, scenario.workflow_id),
                fixture=fixture,
                signature=actual_signature,
            )
        parent_violations = _parent_chain_violations(panel)
        recorder.increment("parenting.violations", len(parent_violations))
        after_widgets = _widget_count()
        recorder.mark(
            "production_trace.end",
            widget_count=after_widgets,
            widget_delta=after_widgets - before_widgets,
            projection_complete=trace_shell.projection_complete,
        )
        signature_matched = expected_signature == actual_signature
        mismatches = [] if signature_matched else ["settled_signature"]
        if partial_orphan_field_cards:
            mismatches.append("partial_orphan_field_cards")
        return {
            "scenario_id": scenario.workflow_id,
            "iteration": iteration,
            "projection_completed": trace_shell.projection_complete,
            "signature_matched": signature_matched,
            "signature_hash": stable_json_hash(actual_signature),
            "expected_signature_hash": expected_hash,
            "actual_signature": actual_signature,
            "partial_orphan_field_cards": partial_orphan_field_cards,
            "parent_chain_violations": parent_violations,
            "override_action_log": list(trace_shell.action_log),
            "widget_count_before": before_widgets,
            "widget_count_after": after_widgets,
            "counters": recorder.counters,
            "timings_ms": recorder.timings_ms,
            "events": [event.to_json() for event in recorder.events],
            "mismatches": mismatches,
        }
    finally:
        host.close()
        host.deleteLater()
        _drain_qt_events(25)


def _workflow_from_fixture(
    fixture: Mapping[str, Any],
) -> tuple[WorkflowState, dict[str, Any]]:
    """Materialize captured canonical cube documents into runtime workflow state."""

    workflow = WorkflowState()
    raw_global_overrides = fixture.get("global_overrides", {})
    workflow.global_overrides = (
        copy.deepcopy(cast(GlobalOverrideMap, raw_global_overrides))
        if isinstance(raw_global_overrides, dict)
        else {}
    )
    definitions: dict[str, Any] = {}
    root_definitions = fixture.get("node_definitions")
    live_definitions: dict[str, Any] = (
        dict(root_definitions) if isinstance(root_definitions, Mapping) else {}
    )
    cubes = fixture.get("cubes", [])
    if not isinstance(cubes, list):
        return workflow, definitions
    for cube_payload in cubes:
        if not isinstance(cube_payload, Mapping):
            continue
        cube_buffer = cube_payload.get("cube_buffer")
        if not isinstance(cube_buffer, Mapping):
            continue
        document = validate_canonical_cube_document(cube_buffer)
        runtime_graph = materialize_cube_runtime_graph(document)
        graph_definitions = runtime_graph.get("definitions")
        if isinstance(graph_definitions, dict):
            graph_definitions.update(live_definitions)
            wrapper_definitions = _wrapper_definitions_with_choice_fallbacks(
                runtime_graph
            )
            graph_definitions.update(wrapper_definitions)
        runtime_definitions = runtime_graph.get("definitions")
        if isinstance(runtime_definitions, Mapping):
            definitions.update(runtime_definitions)
        alias = str(cube_payload.get("alias", document.display_name))
        ui_payload: dict[str, object] = {
            "canonical_cube": document.to_metadata_payload(),
            "content_hash": str(cube_payload.get("content_hash", "")),
            "node_behavior_runtime": NodeBehaviorRuntimeState(),
        }
        cube_state = CubeState(
            cube_id=document.cube_id,
            version=document.version,
            alias=alias,
            original_cube=copy.deepcopy(runtime_graph),
            buffer=copy.deepcopy(runtime_graph),
            display_name=str(cube_payload.get("display_name", document.display_name)),
            ui=ui_payload,
        )
        workflow.cubes[alias] = cube_state
        workflow.stack_order.append(alias)
    if isinstance(root_definitions, Mapping):
        definitions.update(root_definitions)
    return workflow, definitions


def _write_production_target(
    *,
    fixture_path: Path,
    fixture: Mapping[str, Any],
    signature: Mapping[str, Any],
) -> None:
    """Persist the observed production settled signature into one fixture."""

    updated = dict(fixture)
    signature_payload = copy.deepcopy(dict(signature))
    updated["production_settled_signature"] = signature_payload
    updated["production_settled_signature_hash"] = stable_json_hash(signature_payload)
    updated["fixture_hash"] = stable_json_hash(updated)
    write_json(fixture_path, updated)


def _wrapper_definitions_with_choice_fallbacks(
    runtime_graph: Mapping[str, object],
) -> dict[str, Any]:
    """Return renderable wrapper definitions for standalone fixture projection."""

    wrapper_index = SubgraphWrapperDefinitionIndex.from_runtime_graph(runtime_graph)
    definitions: dict[str, Any] = {}
    nodes = runtime_graph.get("nodes")
    if not isinstance(nodes, Mapping):
        return definitions
    for node_payload in nodes.values():
        if not isinstance(node_payload, Mapping):
            continue
        class_type = node_payload.get("class_type")
        if not isinstance(class_type, str):
            continue
        definition = wrapper_index.definition_for_class_type(class_type)
        if definition is None:
            continue
        definitions[class_type] = _definition_with_list_choice_fallbacks(definition)
    return definitions


def _definition_with_list_choice_fallbacks(
    definition: Mapping[str, object],
) -> dict[str, object]:
    """Add minimal LIST options when fixture metadata has only authored defaults."""

    patched = copy.deepcopy(dict(definition))
    input_section = patched.get("input")
    if not isinstance(input_section, dict):
        return patched
    for section_name in ("required", "optional"):
        section = input_section.get(section_name)
        if not isinstance(section, dict):
            continue
        for field_key, field_spec in list(section.items()):
            section[field_key] = _field_spec_with_list_choice_fallback(field_spec)
    return patched


def _field_spec_with_list_choice_fallback(field_spec: object) -> object:
    """Return a field spec with a renderable single fallback option when needed."""

    if not isinstance(field_spec, list) or not field_spec:
        return field_spec
    first = field_spec[0]
    if isinstance(first, list) and first:
        return field_spec
    if first != "LIST":
        return field_spec
    metadata = (
        field_spec[1] if len(field_spec) > 1 and isinstance(field_spec[1], dict) else {}
    )
    options = metadata.get("options") if isinstance(metadata, dict) else None
    if isinstance(options, list | tuple) and options:
        return field_spec
    fallback = metadata.get("default") if isinstance(metadata, dict) else None
    if fallback is None or isinstance(fallback, list | dict):
        fallback = "Fixture Placeholder"
    patched = list(field_spec)
    patched[0] = [str(fallback)]
    return patched


def _build_editor_panel(
    *,
    host: QWidget,
    workflow_id: str,
    definitions: Mapping[str, Any],
) -> EditorPanel:
    """Create a real editor panel with fixture-backed collaborators."""

    _configure_editor_control_registry()
    gateway = FixtureNodeDefinitionGateway(definitions)
    panel = EditorPanel(
        node_definition_gateway=gateway,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        node_behavior_service=NodeBehaviorService(node_definition_gateway=gateway),
        workflow_id=workflow_id,
    )
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(cast(QWidget, panel))
    return panel


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


def _build_trace_shell(
    *,
    workflow_id: str,
    workflow: WorkflowState,
    panel: EditorPanel,
    recorder: ProjectionTraceRecorder,
) -> _TraceShell:
    """Create the minimum shell surface needed by MainWindow refresh orchestration."""

    trace = _TraceShell(
        shell=None,
        override_manager=_TraceOverrideManager(recorder=recorder),
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
        generationActionCluster=_TraceGenerationActionCluster(recorder=recorder),
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


class _TraceOverrideManager:
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

        self._recorder.increment(
            "override.apply_without_snapshot_fallback.calls",
        )
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


class _TraceGenerationActionCluster:
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


@contextmanager
def _instrument_projection(recorder: ProjectionTraceRecorder) -> Iterator[None]:
    """Temporarily wrap production methods with timing/counter instrumentation."""

    patches: list[tuple[Any, str, object]] = []

    def patch_attribute(
        owner: Any,
        attribute_name: str,
        replacement: object,
    ) -> None:
        """Patch one attribute and remember how to restore it."""

        original = getattr(owner, attribute_name)
        patches.append((owner, attribute_name, original))
        setattr(owner, attribute_name, replacement)

    def patch_method(
        owner: type[Any],
        method_name: str,
        event_name: str,
        counter_name: str,
        detail_reader: Callable[[Any, tuple[Any, ...], dict[str, Any]], dict[str, Any]]
        | None = None,
    ) -> None:
        """Patch one method and remember how to restore it."""

        original = getattr(owner, method_name)

        def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
            """Record one production method call and delegate to the original."""

            recorder.increment(counter_name)
            details = detail_reader(self, args, kwargs) if detail_reader else {}
            with recorder.timed(event_name, **details):
                return original(self, *args, **kwargs)

        patch_attribute(owner, method_name, wrapped)

    def patch_function(
        owner: Any,
        function_name: str,
        event_name: str,
        counter_name: str,
        detail_reader: Callable[[tuple[Any, ...], dict[str, Any]], dict[str, Any]]
        | None = None,
    ) -> None:
        """Patch one module-level function and remember how to restore it."""

        original = getattr(owner, function_name)

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            """Record one production function call and delegate to the original."""

            recorder.increment(counter_name)
            details = detail_reader(args, kwargs) if detail_reader else {}
            with recorder.timed(event_name, **details):
                return original(*args, **kwargs)

        patch_attribute(owner, function_name, wrapped)

    patch_method(
        EditorPanelProjectionCoordinator,
        "load_all_cubes",
        "production.editor.load_all_cubes",
        "projection.load_all_cubes.calls",
        lambda _self, args, _kwargs: {"cube_entries": len(args[0]) if args else 0},
    )
    patch_method(
        EditorPanelProjectionCoordinator,
        "_prepare_projection",
        "production.editor.prepare_projection",
        "projection.prepare_projection.calls",
    )
    patch_method(
        EditorPanelProjectionCoordinator,
        "_build_ordered_widgets",
        "production.editor.build_ordered_widgets",
        "projection.build_ordered_widgets.calls",
    )
    patch_method(
        EditorPanelProjectionCoordinator,
        "_repopulate_layout",
        "production.editor.repopulate_layout",
        "projection.repopulate_layout.calls",
        lambda _self, args, _kwargs: {"ordered_widgets": len(args[0]) if args else 0},
    )
    patch_method(
        EditorPanelProjectionCoordinator,
        "_schedule_projected_cube_builds",
        "production.editor.schedule_projected_cube_builds",
        "projection.schedule_projected_cube_builds.calls",
        lambda _self, args, _kwargs: {"projected_builds": len(args[0]) if args else 0},
    )
    patch_method(
        EditorPanelProjectionCoordinator,
        "_reveal_projected_cube_build",
        "production.editor.reveal_projected_cube_build",
        "projection.reveal_projected_cube_build.calls",
        lambda _self, args, _kwargs: {
            "cube_alias": getattr(args[0], "cube_alias", "") if args else ""
        },
    )
    patch_method(
        EditorPanelProjectionCoordinator,
        "_reveal_projected_cube_builds",
        "production.editor.reveal_projected_cube_builds",
        "projection.reveal_projected_cube_builds.calls",
        lambda _self, args, _kwargs: {"projected_builds": len(args[0]) if args else 0},
    )
    patch_method(
        EditorPanelProjectionCoordinator,
        "_refresh_visibility",
        "production.editor.refresh_visibility",
        "projection.refresh_visibility.calls",
    )
    patch_method(
        EditorPanelProjectionCoordinator,
        "begin_build_cube_widget",
        "production.cube.begin_build_cube_widget",
        "cube.begin_build_cube_widget.calls",
        lambda _self, args, _kwargs: {"cube_alias": str(args[0]) if args else ""},
    )
    patch_method(
        CubeSectionBuildSession,
        "step",
        "production.cube.build_step",
        "cube.build_step.calls",
        lambda self, _args, _kwargs: {
            "cube_alias": getattr(self, "_route_key", ""),
            "next_index": getattr(self, "_next_index", -1),
        },
    )
    patch_method(
        CubeSectionBuildSession,
        "finish",
        "production.cube.finish",
        "cube.finish.calls",
        lambda self, _args, _kwargs: {
            "cube_alias": getattr(self, "_route_key", ""),
            "node_count": len(getattr(self, "_node_order", ())),
        },
    )
    patch_method(
        NodeCardBuilder,
        "build_node_card",
        "production.node_card.build_node_card",
        "node_card.build.calls",
        lambda _self, _args, kwargs: {
            "cube_alias": kwargs.get("alias", ""),
            "node_name": kwargs.get("node_name", ""),
            "node_class": kwargs.get("node_type", ""),
            "field_count": len(kwargs.get("field_specs", {})),
        },
    )
    patch_method(
        NodeCardBuilder,
        "_create_title_row",
        "production.node_card.create_title_row",
        "node_card.title_row.calls",
        lambda _self, _args, kwargs: {
            "node_name": kwargs.get("node_name", ""),
            "node_class": kwargs.get("node_type", ""),
            "field_count": len(kwargs.get("field_specs", {})),
        },
    )
    patch_method(
        NodeCardBuilder,
        "_add_input_row",
        "production.node_card.add_input_row",
        "node_card.input_row.calls",
        lambda _self, _args, kwargs: {
            "label": kwargs.get("label", ""),
            "widget_type": type(kwargs.get("widget")).__name__,
        },
    )
    patch_method(
        NodeCardBuilder,
        "add_n_column_row",
        "production.node_card.add_n_column_row",
        "node_card.n_column_row.calls",
        lambda _self, _args, kwargs: {
            "field_count": len(kwargs.get("fields", ())),
            "node_name": kwargs.get("node_name", ""),
        },
    )
    patch_method(
        NodeCardBuilder,
        "_create_field_for_key",
        "production.field.create_field_for_key",
        "field.create.calls",
        lambda _self, _args, kwargs: _field_spec_details(
            kwargs.get("field_spec"),
            cube_alias=kwargs.get("alias", ""),
            node_name=kwargs.get("node_name", ""),
        ),
    )
    patch_function(
        node_card_view,
        "build_widget_for_field_spec",
        "production.field.factory",
        "field.factory.calls",
        lambda _args, kwargs: _field_spec_details(kwargs.get("field_spec")),
    )
    patch_function(
        field_row_view,
        "_apply_field_row_divider_style",
        "production.field_row.apply_divider_style",
        "field_row.divider_style.calls",
        lambda args, _kwargs: {"widget_type": type(args[0]).__name__ if args else ""},
    )
    patch_function(
        field_row_view,
        "bind_fluent_tooltip",
        "production.field_row.bind_tooltip",
        "field_row.bind_tooltip.calls",
        lambda args, _kwargs: {"target_count": max(0, len(args) - 2)},
    )
    patch_function(
        node_card_view,
        "bind_fluent_tooltip",
        "production.node_card.bind_tooltip",
        "node_card.bind_tooltip.calls",
        lambda args, _kwargs: {"target_count": max(0, len(args) - 2)},
    )
    patch_method(
        NodeBehaviorService,
        "build_snapshot",
        "production.behavior.build_snapshot",
        "behavior.build_snapshot.calls",
        lambda _self, _args, kwargs: {
            "callsite": _behavior_snapshot_callsite(),
            "cube_count": len(kwargs.get("cube_states", {})),
            "stack_order_count": len(kwargs.get("stack_order", ())),
            "workflow_override_count": len(kwargs.get("workflow_overrides") or {}),
            "search_hidden_key_count": len(kwargs.get("search_hidden_keys") or ()),
            "override_hidden_field_key_count": len(
                kwargs.get("override_hidden_field_keys") or ()
            ),
            "node_search_text": str(kwargs.get("node_search_text") or ""),
            "search_matching_node_count": len(
                kwargs.get("search_matching_nodes") or ()
            ),
        },
    )
    try:
        yield
    finally:
        for owner, method_name, original in reversed(patches):
            setattr(owner, method_name, original)


def _field_spec_details(
    field_spec: object,
    *,
    cube_alias: object = "",
    node_name: object = "",
) -> dict[str, Any]:
    """Return trace details for one resolved field spec."""

    field_behavior = getattr(field_spec, "field_behavior", None)
    presentation = getattr(field_behavior, "presentation", None)
    return {
        "cube_alias": str(cube_alias or getattr(field_spec, "cube_alias", "") or ""),
        "node_name": str(node_name or getattr(field_spec, "node_name", "") or ""),
        "node_class": str(getattr(field_spec, "class_type", "") or ""),
        "field_key": str(getattr(field_spec, "field_key", "") or ""),
        "field_type": str(getattr(field_spec, "field_type", "") or ""),
        "presentation": str(getattr(presentation, "value", presentation) or ""),
        "value_source": str(
            getattr(getattr(field_spec, "value_source", None), "value", "") or ""
        ),
    }


def _behavior_snapshot_callsite() -> str:
    """Return the nearest application frame that requested a behavior snapshot."""

    for frame in inspect.stack()[2:12]:
        path = Path(frame.filename)
        if "substitute" not in path.parts:
            continue
        if path.name == "behavior_service.py":
            continue
        return f"{path.name}:{frame.function}:{frame.lineno}"
    return ""


def _signature_from_panel(
    *,
    workflow_id: str,
    workflow: WorkflowState,
    panel: EditorPanel,
) -> EditorSettledSignature:
    """Build a settled signature from rendered panel registries."""

    cube_sections: list[CubeSectionSignature] = []
    card_wrappers = getattr(panel, "card_wrappers", {})
    input_widgets = getattr(panel, "input_widgets_by_field_key", {})
    for alias in workflow.stack_order:
        cube_state = workflow.cubes[alias]
        nodes = cube_state.buffer.get("nodes", {})
        node_cards: list[NodeCardSignature] = []
        if isinstance(nodes, Mapping):
            for node_name in sorted(nodes):
                node_payload = nodes[node_name]
                if not isinstance(node_payload, Mapping):
                    continue
                wrapper = card_wrappers.get((alias, node_name))
                fields = _field_signatures(
                    alias=alias,
                    node_name=str(node_name),
                    node_payload=node_payload,
                    input_widgets=input_widgets,
                )
                node_cards.append(
                    NodeCardSignature(
                        node_name=str(node_name),
                        node_class=str(node_payload.get("class_type", "")),
                        visible=wrapper is not None,
                        enabled=bool(getattr(wrapper, "isEnabled", lambda: True)()),
                        fields=fields,
                    )
                )
        cube_sections.append(
            CubeSectionSignature(
                alias=alias,
                cube_id=cube_state.cube_id,
                version=cube_state.version,
                node_cards=tuple(node_cards),
            )
        )
    return EditorSettledSignature(
        workflow_id=workflow_id,
        cube_sections=tuple(cube_sections),
        parent_chain_violations=tuple(_parent_chain_violations(panel)),
    )


def _field_signatures(
    *,
    alias: str,
    node_name: str,
    node_payload: Mapping[str, Any],
    input_widgets: Mapping[object, object],
) -> tuple[FieldSignature, ...]:
    """Build field signatures from rendered input widgets and runtime inputs."""

    inputs = node_payload.get("inputs", {})
    input_mapping = inputs if isinstance(inputs, Mapping) else {}
    field_keys = {str(key) for key in input_mapping if isinstance(key, str)}
    for key in input_widgets:
        if (
            isinstance(key, tuple)
            and len(key) == 3
            and key[0] == alias
            and key[1] == node_name
            and isinstance(key[2], str)
        ):
            field_keys.add(key[2])
    fields: list[FieldSignature] = []
    for field_key in sorted(field_keys):
        widget = input_widgets.get((alias, node_name, field_key))
        visible = widget is not None
        fields.append(
            FieldSignature(
                field_key=field_key,
                value_repr=repr(input_mapping.get(field_key)),
                visible=visible,
            )
        )
    return tuple(fields)


def _partial_orphan_field_card_refs(signature: Mapping[str, Any]) -> list[str]:
    """Return cards that lost their wrapper after registering visible field widgets."""

    refs: list[str] = []
    cube_sections = signature.get("cube_sections")
    if not isinstance(cube_sections, Sequence) or isinstance(
        cube_sections, (str, bytes)
    ):
        return refs
    for cube_section in cube_sections:
        if not isinstance(cube_section, Mapping):
            continue
        alias = str(cube_section.get("alias", ""))
        node_cards = cube_section.get("node_cards")
        if not isinstance(node_cards, Sequence) or isinstance(node_cards, (str, bytes)):
            continue
        for node_card in node_cards:
            if not isinstance(node_card, Mapping):
                continue
            if bool(node_card.get("visible")):
                continue
            fields = node_card.get("fields")
            if not isinstance(fields, Sequence) or isinstance(fields, (str, bytes)):
                continue
            has_visible_field = any(
                isinstance(field, Mapping) and bool(field.get("visible"))
                for field in fields
            )
            if has_visible_field:
                refs.append(f"{alias}:{node_card.get('node_name', '')}")
    return sorted(refs)


def _parent_chain_violations(panel: EditorPanel) -> list[str]:
    """Return node-card wrappers that are not parented under their cube section."""

    violations: list[str] = []
    card_wrappers = getattr(panel, "card_wrappers", {})
    if not isinstance(card_wrappers, Mapping):
        return violations
    for key, wrapper in card_wrappers.items():
        if not isinstance(key, tuple) or len(key) != 2:
            continue
        alias = str(key[0])
        node_name = str(key[1])
        if not isinstance(wrapper, QWidget):
            continue
        if not _has_cube_ancestor(wrapper, alias):
            violations.append(f"{alias}:{node_name}")
    return sorted(violations)


def _has_cube_ancestor(widget: QWidget, alias: str) -> bool:
    """Return whether a widget has the expected cube section in its parent chain."""

    current = widget.parentWidget()
    while current is not None:
        if current.property("cube_alias") == alias:
            return True
        current = current.parentWidget()
    return False


def _drain_until_complete(trace_shell: _TraceShell, *, max_turns: int) -> None:
    """Process Qt events until projection completion or a bounded turn limit."""

    app = QApplication.instance()
    if app is None:
        return
    for _turn in range(max_turns):
        app.processEvents()
        if trace_shell.projection_complete:
            return
    raise TimeoutError("Production editor projection did not complete in the rig.")


def _drain_qt_events(turns: int) -> None:
    """Process a fixed number of Qt events."""

    app = QApplication.instance()
    if app is None:
        return
    for _turn in range(turns):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _widget_count() -> int:
    """Return the current QApplication widget count."""

    app = QApplication.instance()
    if app is None:
        return 0
    return len(cast(QApplication, app).allWidgets())


def _mark_complete(
    trace_shell: _TraceShell,
    recorder: ProjectionTraceRecorder,
) -> None:
    """Mark shell projection completion in the trace."""

    trace_shell.projection_complete = True
    _record_action(trace_shell, recorder, "projection_complete")


def _record_action(
    trace_shell: _TraceShell,
    recorder: ProjectionTraceRecorder,
    action: str,
) -> None:
    """Record a shell-level action in both log and counter form."""

    trace_shell.action_log.append(action)
    recorder.increment(f"shell.{action}.calls")
    recorder.mark(f"shell.{action}")


def _begin_busy(
    trace_shell: _TraceShell,
    recorder: ProjectionTraceRecorder,
    workflow_id: str,
    message: str,
) -> str:
    """Record busy-overlay entry and return a token."""

    _record_action(trace_shell, recorder, "begin_editor_busy")
    recorder.mark(
        "shell.begin_editor_busy.details", workflow_id=workflow_id, message=message
    )
    return f"busy:{workflow_id}:{message}"


def _end_busy(
    trace_shell: _TraceShell,
    recorder: ProjectionTraceRecorder,
    token: object,
) -> None:
    """Record busy-overlay exit."""

    _record_action(trace_shell, recorder, "end_editor_busy")
    recorder.mark("shell.end_editor_busy.details", token=repr(token))


def _budget_summary(iteration_reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return pass/fail correctness budgets for production trace reports."""

    signature_mismatches = sum(
        0 if bool(report.get("signature_matched")) else 1
        for report in iteration_reports
    )
    parent_violations = sum(
        len(report.get("parent_chain_violations", ()))
        if isinstance(report.get("parent_chain_violations"), list)
        else 0
        for report in iteration_reports
    )
    incomplete = sum(
        0 if bool(report.get("projection_completed")) else 1
        for report in iteration_reports
    )
    partial_orphans = sum(
        len(report.get("partial_orphan_field_cards", ()))
        if isinstance(report.get("partial_orphan_field_cards"), list)
        else 0
        for report in iteration_reports
    )
    return {
        "projection_incomplete": {
            "actual": incomplete,
            "limit": 0,
            "passed": incomplete == 0,
        },
        "partial_orphan_field_cards": {
            "actual": partial_orphans,
            "limit": 0,
            "passed": partial_orphans == 0,
        },
        "settled_signature_mismatches": {
            "actual": signature_mismatches,
            "limit": 0,
            "passed": signature_mismatches == 0,
        },
        "parenting.violations": {
            "actual": parent_violations,
            "limit": 0,
            "passed": parent_violations == 0,
        },
    }


def _aggregate_summary(
    iteration_reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return scenario-grouped timing and work-counter summaries."""

    grouped_reports: dict[str, list[Mapping[str, Any]]] = {}
    for report in iteration_reports:
        scenario_id = str(report.get("scenario_id", ""))
        grouped_reports.setdefault(scenario_id, []).append(report)
    return {
        scenario_id: _aggregate_scenario_reports(reports)
        for scenario_id, reports in sorted(grouped_reports.items())
    }


def _aggregate_scenario_reports(
    reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return aggregate timings and counters for one scenario."""

    return {
        "iterations": len(reports),
        "timings_ms": _aggregate_numeric_mapping(reports, "timings_ms"),
        "counter_totals": _sum_numeric_mapping(reports, "counters"),
    }


def _aggregate_numeric_mapping(
    reports: Sequence[Mapping[str, Any]],
    key: str,
) -> dict[str, dict[str, float]]:
    """Return min/mean/max/p95 for numeric values in nested report mappings."""

    values_by_name: dict[str, list[float]] = {}
    for report in reports:
        mapping = report.get(key)
        if not isinstance(mapping, Mapping):
            continue
        for name, value in mapping.items():
            if isinstance(value, int | float):
                values_by_name.setdefault(str(name), []).append(float(value))
    return {
        name: _numeric_stats(values)
        for name, values in sorted(values_by_name.items())
        if values
    }


def _sum_numeric_mapping(
    reports: Sequence[Mapping[str, Any]],
    key: str,
) -> dict[str, float]:
    """Return totals for numeric values in nested report mappings."""

    totals: dict[str, float] = {}
    for report in reports:
        mapping = report.get(key)
        if not isinstance(mapping, Mapping):
            continue
        for name, value in mapping.items():
            if isinstance(value, int | float):
                totals[str(name)] = totals.get(str(name), 0.0) + float(value)
    return dict(sorted(totals.items()))


def _numeric_stats(values: Sequence[float]) -> dict[str, float]:
    """Return stable summary statistics for one numeric sample set."""

    ordered = sorted(values)
    p95_index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1))
    return {
        "min": round(ordered[0], 3),
        "mean": round(sum(ordered) / len(ordered), 3),
        "max": round(ordered[-1], 3),
        "p95": round(ordered[p95_index], 3),
    }


__all__ = ["trace_production_scenarios"]
