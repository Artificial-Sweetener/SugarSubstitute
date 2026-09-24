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
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, cast

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.node_behavior import NodeBehaviorRuntimeState
from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.application.localization import (
    ActiveComfyNodeCatalogStore,
    NodePresentationService,
)
from substitute.domain.common import GlobalOverrideMap
from substitute.domain.cubes import (
    SubgraphWrapperDefinitionIndex,
    materialize_cube_runtime_graph,
    validate_canonical_cube_document,
)
from substitute.domain.workflow.models import CubeState, WorkflowState
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.shell.main_window_editor_surface_adapter import (
    MainWindowEditorSurfaceAdapter,
)

from .fake_gateways import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    FixtureNodeDefinitionGateway,
)
from .fixtures import read_json, stable_json_hash, workflow_fixture_path, write_json
from .production_instrumentation import instrument_projection
from .qt_harness import create_hidden_host, ensure_qapplication
from .scenarios import WorkflowScenario
from .signatures import (
    CubeSectionSignature,
    EditorSettledSignature,
    FieldSignature,
    NodeCardSignature,
)
from .trace_events import ProjectionTraceRecorder

_SETTLE_TURN_TIMEOUT_MS = 20


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
            host = create_hidden_host(show_window=True)
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
        instrument_projection(recorder),
        recorder.timed(
            "production.total_elapsed_ms",
            workflow_id=scenario.workflow_id,
            activation=activation,
        ),
    ):
        MainWindowEditorSurfaceAdapter(trace_shell.shell).refresh_editor_surface(
            scenario.workflow_id,
            force=False,
            on_complete=lambda _result: _mark_complete(trace_shell, recorder),
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
    host = create_hidden_host(show_window=True)
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
            instrument_projection(recorder),
            recorder.timed(
                "production.total_elapsed_ms",
                workflow_id=scenario.workflow_id,
            ),
        ):
            MainWindowEditorSurfaceAdapter(trace_shell.shell).refresh_editor_surface(
                scenario.workflow_id,
                force=False,
                on_complete=lambda _result: _mark_complete(trace_shell, recorder),
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
    """Run a bounded Qt event loop until projection completion is observable."""

    app = QApplication.instance()
    if app is None:
        return
    if trace_shell.projection_complete:
        return
    loop = QEventLoop()
    completion_poll = QTimer()
    completion_poll.setInterval(1)
    completion_poll.timeout.connect(
        lambda: loop.quit() if trace_shell.projection_complete else None
    )
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    completion_poll.start()
    timeout.start(max(1, max_turns) * _SETTLE_TURN_TIMEOUT_MS)
    loop.exec()
    completion_poll.stop()
    timeout.stop()
    if not trace_shell.projection_complete:
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
