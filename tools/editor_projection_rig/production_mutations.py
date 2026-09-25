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

"""Trace production editor mutations against captured workflow fixtures."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from substitute.domain.workflow.models import WorkflowState
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.shell.main_window_editor_surface_adapter import (
    MainWindowEditorSurfaceAdapter,
)

from .fixtures import read_json, stable_json_hash, workflow_fixture_path, write_json
from .production_fixture import workflow_from_fixture
from .production_instrumentation import instrument_projection
from .production_mount import build_editor_panel, build_trace_shell
from .production_signatures import (
    parent_chain_violations,
    partial_orphan_field_card_refs,
    signature_from_panel,
)
from .production_switch import trace_inflight_workflow_switch
from .qt_harness import create_hidden_host, drain_qt_events, drain_until, widget_count
from .scenarios import WorkflowScenario
from .trace_events import ProjectionTraceRecorder


def trace_production_mutations(
    scenarios: Sequence[WorkflowScenario],
    *,
    fixtures_dir: Path,
    report_path: Path,
    iterations: int = 1,
    settle_turns: int = 500,
) -> dict[str, Any]:
    """Trace incremental construction, reorder, replacement, and clean refresh."""

    scenario_reports: list[dict[str, Any]] = []
    switch_reports: list[dict[str, Any]] = []
    for iteration in range(1, iterations + 1):
        for scenario in scenarios:
            scenario_report = _trace_scenario_mutations(
                scenario,
                fixtures_dir=fixtures_dir,
                settle_turns=settle_turns,
            )
            scenario_report["iteration"] = iteration
            scenario_reports.append(scenario_report)
        switch_report = trace_inflight_workflow_switch(
            scenarios,
            fixtures_dir=fixtures_dir,
            settle_turns=settle_turns,
        )
        if switch_report is not None:
            switch_report["iteration"] = iteration
            switch_reports.append(switch_report)
    budgets = mutation_budget_summary(scenario_reports)
    budgets["inflight_workflow_switch"] = _zero_budget(
        sum(not bool(report.get("passed")) for report in switch_reports)
    )
    report = {
        "schema_version": 1,
        "mode": "production_mutations",
        "iterations": iterations,
        "scenario_reports": scenario_reports,
        "inflight_workflow_switch_reports": switch_reports,
        "budgets": budgets,
    }
    write_json(report_path, report)
    return report


def mutation_budget_summary(
    scenario_reports: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, int | bool]]:
    """Return zero-tolerance correctness budgets for mutation reports."""

    operations = [
        operation
        for scenario in scenario_reports
        for operation in cast(
            Sequence[Mapping[str, Any]],
            scenario.get("operations", ()),
        )
    ]
    incomplete = sum(
        int(operation.get("completion_count", 0)) != 1 for operation in operations
    )
    violations = sum(
        len(cast(Sequence[object], operation.get("parent_chain_violations", ())))
        for operation in operations
    )
    partial_orphans = sum(
        len(cast(Sequence[object], operation.get("partial_orphan_field_cards", ())))
        for operation in operations
    )
    identity_failures = sum(
        not bool(operation.get("expected_identity_preserved"))
        for operation in operations
    )
    unexpected_builds = sum(
        not bool(operation.get("construction_budget_passed"))
        for operation in operations
    )
    return {
        "incomplete_operations": _zero_budget(incomplete),
        "parent_chain_violations": _zero_budget(violations),
        "partial_orphan_field_cards": _zero_budget(partial_orphans),
        "identity_failures": _zero_budget(identity_failures),
        "unexpected_construction": _zero_budget(unexpected_builds),
    }


def _trace_scenario_mutations(
    scenario: WorkflowScenario,
    *,
    fixtures_dir: Path,
    settle_turns: int,
) -> dict[str, Any]:
    """Trace one fixture from a one-cube mount through representative mutations."""

    fixture = read_json(workflow_fixture_path(fixtures_dir, scenario.workflow_id))
    source_workflow, definitions = workflow_from_fixture(fixture)
    aliases = list(source_workflow.stack_order)
    if len(aliases) < 3:
        raise ValueError(f"Mutation trace requires three cubes: {scenario.workflow_id}")
    workflow = WorkflowState(
        cubes={aliases[0]: source_workflow.cubes[aliases[0]]},
        stack_order=[aliases[0]],
        global_overrides=copy.deepcopy(source_workflow.global_overrides),
    )
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
        recorder=ProjectionTraceRecorder(),
    )
    panel.mainwindow = trace_shell.shell
    operations: list[dict[str, Any]] = []
    try:
        operations.append(
            _trace_refresh(
                name="initial_small_mount",
                workflow=workflow,
                panel=panel,
                shell=trace_shell.shell,
                settle_turns=settle_turns,
                expected_preserved={},
                maximum_cube_builds=1,
            )
        )
        for index, operation_name in ((1, "insert_to_medium"), (2, "insert_to_large")):
            preserved = _widget_identities(panel)
            alias = aliases[index]
            workflow.cubes[alias] = source_workflow.cubes[alias]
            workflow.stack_order.append(alias)
            operations.append(
                _trace_insert(
                    name=operation_name,
                    cube_alias=alias,
                    workflow=workflow,
                    panel=panel,
                    settle_turns=settle_turns,
                    expected_preserved=preserved,
                )
            )
        preserved = _widget_identities(panel)
        workflow.stack_order.reverse()
        operations.append(
            _trace_refresh(
                name="reorder_large",
                workflow=workflow,
                panel=panel,
                shell=trace_shell.shell,
                settle_turns=settle_turns,
                expected_preserved=preserved,
                maximum_cube_builds=0,
            )
        )
        preserved = _widget_identities(panel)
        replaced_alias = workflow.stack_order[1]
        workflow.cubes[replaced_alias] = copy.deepcopy(workflow.cubes[replaced_alias])
        panel.mark_cube_sections_stale(
            (replaced_alias,),
            reason="baseline_node_field_replacement",
        )
        operations.append(
            _trace_refresh(
                name="replace_one_cube_node_field_surface",
                workflow=workflow,
                panel=panel,
                shell=trace_shell.shell,
                settle_turns=settle_turns,
                expected_preserved={
                    alias: identity
                    for alias, identity in preserved.items()
                    if alias != replaced_alias
                },
                maximum_cube_builds=1,
            )
        )
        preserved = _widget_identities(panel)
        operations.append(
            _trace_refresh(
                name="clean_refresh",
                workflow=workflow,
                panel=panel,
                shell=trace_shell.shell,
                settle_turns=settle_turns,
                expected_preserved=preserved,
                maximum_cube_builds=0,
            )
        )
        return {"scenario_id": scenario.workflow_id, "operations": operations}
    finally:
        host.close()
        host.deleteLater()
        drain_qt_events(25)


def _trace_refresh(
    *,
    name: str,
    workflow: WorkflowState,
    panel: EditorPanel,
    shell: object,
    settle_turns: int,
    expected_preserved: Mapping[str, int],
    maximum_cube_builds: int,
) -> dict[str, Any]:
    """Trace one production shell refresh operation."""

    completion_count = 0

    def complete(_result: object) -> None:
        """Count production surface completion publication."""

        nonlocal completion_count
        completion_count += 1

    recorder = ProjectionTraceRecorder()
    before_widgets = widget_count()
    started_at = perf_counter()
    with instrument_projection(recorder):
        result = MainWindowEditorSurfaceAdapter(shell).refresh_editor_surface(
            str(getattr(panel, "_workflow_id", "")),
            force=False,
            on_complete=complete,
        )
        if result.error:
            raise RuntimeError(result.error)
        drain_until(lambda: completion_count == 1, max_turns=settle_turns)
    return _operation_report(
        name=name,
        workflow=workflow,
        panel=panel,
        recorder=recorder,
        completion_count=completion_count,
        elapsed_ms=(perf_counter() - started_at) * 1000.0,
        before_widgets=before_widgets,
        expected_preserved=expected_preserved,
        maximum_cube_builds=maximum_cube_builds,
    )


def _trace_insert(
    *,
    name: str,
    cube_alias: str,
    workflow: WorkflowState,
    panel: EditorPanel,
    settle_turns: int,
    expected_preserved: Mapping[str, int],
) -> dict[str, Any]:
    """Trace one incremental cube-section insertion."""

    completion_count = 0

    def complete() -> None:
        """Count incremental completion publication."""

        nonlocal completion_count
        completion_count += 1

    recorder = ProjectionTraceRecorder()
    before_widgets = widget_count()
    started_at = perf_counter()
    with instrument_projection(recorder):
        panel.insert_cube_section(
            cube_alias,
            workflow.cubes[cube_alias],
            cube_states=cast(dict[str, object], workflow.cubes),
            stack_order=workflow.stack_order,
            on_complete=complete,
            completion_phase="complete",
        )
        drain_until(lambda: completion_count == 1, max_turns=settle_turns)
    return _operation_report(
        name=name,
        workflow=workflow,
        panel=panel,
        recorder=recorder,
        completion_count=completion_count,
        elapsed_ms=(perf_counter() - started_at) * 1000.0,
        before_widgets=before_widgets,
        expected_preserved=expected_preserved,
        maximum_cube_builds=1,
    )


def _operation_report(
    *,
    name: str,
    workflow: WorkflowState,
    panel: EditorPanel,
    recorder: ProjectionTraceRecorder,
    completion_count: int,
    elapsed_ms: float,
    before_widgets: int,
    expected_preserved: Mapping[str, int],
    maximum_cube_builds: int,
) -> dict[str, Any]:
    """Return correctness, identity, construction, and timing evidence."""

    signature = signature_from_panel(
        workflow_id=str(getattr(panel, "_workflow_id", "")),
        workflow=workflow,
        panel=panel,
    ).to_json()
    identities = _widget_identities(panel)
    cube_builds = recorder.counters.get("cube.begin_build_cube_widget.calls", 0)
    return {
        "name": name,
        "elapsed_ms": round(elapsed_ms, 3),
        "completion_count": completion_count,
        "widget_count_before": before_widgets,
        "widget_count_after": widget_count(),
        "cube_build_count": cube_builds,
        "node_card_build_count": recorder.counters.get("node_card.build.calls", 0),
        "field_build_count": recorder.counters.get("field.create.calls", 0),
        "construction_budget_passed": cube_builds <= maximum_cube_builds,
        "expected_identity_preserved": all(
            identities.get(alias) == identity
            for alias, identity in expected_preserved.items()
        ),
        "settled_signature_hash": stable_json_hash(signature),
        "partial_orphan_field_cards": partial_orphan_field_card_refs(signature),
        "parent_chain_violations": parent_chain_violations(panel),
        "counters": recorder.counters,
        "timings_ms": recorder.timings_ms,
    }


def _widget_identities(panel: EditorPanel) -> dict[str, int]:
    """Return mounted cube widget identity by semantic alias."""

    widgets = cast(Mapping[str, object], getattr(panel, "cube_widgets", {}))
    return {alias: id(widget) for alias, widget in widgets.items()}


def _zero_budget(actual: int) -> dict[str, int | bool]:
    """Return a zero-tolerance budget result."""

    return {"actual": actual, "limit": 0, "passed": actual == 0}
