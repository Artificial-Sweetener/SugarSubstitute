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

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QWidget

from substitute.domain.workflow.models import WorkflowState
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.shell.main_window_editor_surface_adapter import (
    MainWindowEditorSurfaceAdapter,
)

from .fixtures import read_json, stable_json_hash, workflow_fixture_path, write_json
from .production_instrumentation import instrument_projection
from .production_fixture import (
    workflow_from_fixture,
    write_production_target as persist_production_target,
)
from .production_mount import (
    build_editor_panel,
    build_trace_shell,
    mark_complete,
)
from .production_report import aggregate_summary, budget_summary
from .qt_harness import (
    create_hidden_host,
    drain_qt_events,
    drain_until,
    ensure_qapplication,
    widget_count,
)
from .scenarios import WorkflowScenario
from .production_signatures import (
    parent_chain_violations,
    partial_orphan_field_card_refs,
    signature_from_panel,
)
from .trace_events import ProjectionTraceRecorder


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
        "aggregates": aggregate_summary(iteration_reports),
        "budgets": budget_summary(iteration_reports),
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
            workflow, definitions = workflow_from_fixture(fixture)
            host = create_hidden_host(show_window=True)
            panel = build_editor_panel(
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
        drain_qt_events(25)


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
    trace_shell = build_trace_shell(
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
    before_widgets = widget_count()
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
            on_complete=lambda _result: mark_complete(trace_shell, recorder),
        )
        drain_until(lambda: trace_shell.projection_complete, max_turns=settle_turns)
    drain_qt_events(10)
    recorder.record_elapsed_between(
        "production.time_to_first_usable_ms",
        start_event="production_trace.start",
        end_event="production.editor.reveal_projected_cube_builds",
    )
    actual_signature = signature_from_panel(
        workflow_id=scenario.workflow_id,
        workflow=workflow,
        panel=panel,
    ).to_json()
    partial_orphan_field_cards = partial_orphan_field_card_refs(actual_signature)
    parent_violations = parent_chain_violations(panel)
    recorder.increment("parenting.violations", len(parent_violations))
    after_widgets = widget_count()
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
    workflow, definitions = workflow_from_fixture(fixture)
    recorder = ProjectionTraceRecorder()
    host = create_hidden_host(show_window=True)
    panel = build_editor_panel(
        host=host,
        workflow_id=scenario.workflow_id,
        definitions=definitions,
    )
    trace_shell = build_trace_shell(
        workflow_id=scenario.workflow_id,
        workflow=workflow,
        panel=panel,
        recorder=recorder,
    )
    panel.mainwindow = trace_shell.shell
    before_widgets = widget_count()
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
                on_complete=lambda _result: mark_complete(trace_shell, recorder),
            )
            drain_until(lambda: trace_shell.projection_complete, max_turns=settle_turns)
        drain_qt_events(10)
        recorder.record_elapsed_between(
            "production.time_to_first_usable_ms",
            start_event="production_trace.start",
            end_event="production.editor.reveal_projected_cube_builds",
        )
        actual_signature = signature_from_panel(
            workflow_id=scenario.workflow_id,
            workflow=workflow,
            panel=panel,
        ).to_json()
        partial_orphan_field_cards = partial_orphan_field_card_refs(actual_signature)
        if write_production_target and partial_orphan_field_cards:
            message = (
                "Refusing to write production settled target with partial orphan "
                f"field cards: {partial_orphan_field_cards!r}"
            )
            raise ValueError(message)
        if write_production_target:
            persist_production_target(
                fixture_path=workflow_fixture_path(fixtures_dir, scenario.workflow_id),
                fixture=fixture,
                signature=actual_signature,
            )
        parent_violations = parent_chain_violations(panel)
        recorder.increment("parenting.violations", len(parent_violations))
        after_widgets = widget_count()
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
        drain_qt_events(25)


__all__ = ["trace_production_scenarios"]
