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

"""Define immutable observations and reports for bundled-workflow audits."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.presentation.editor.panel.cube_section_build_plan import (
    NodeCardBuildOutcome,
)


@dataclass(frozen=True, slots=True)
class AuditFinding:
    """Describe one observed production exception or lifecycle contradiction."""

    workflow: str
    category: str
    code: str
    stage: str
    message: str
    node_id: str = ""
    class_type: str = ""
    field_key: str = ""
    exception_type: str = ""
    traceback: str = ""


@dataclass(frozen=True, slots=True)
class FieldSpecObservation:
    """Persist one production-resolved field contract without interpreting it."""

    field_key: str
    field_type: str
    presentation: str
    control_name: str
    hidden: bool
    value_source: str
    value_type: str
    value_repr: str
    raw_value_type: str
    raw_value_repr: str
    constraints_repr: str
    meta_info_repr: str


@dataclass(frozen=True, slots=True)
class FieldFactoryObservation:
    """Persist one real call into the production field-factory pipeline."""

    node_id: str
    class_type: str
    field_key: str
    field_type: str
    presentation: str
    control_name: str
    value_source: str
    result: str
    widget_type: str
    exception_type: str
    exception_message: str
    traceback: str
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class RuntimeLogObservation:
    """Persist one warning-or-higher Python log record from a workflow load."""

    level: str
    logger: str
    message: str
    traceback: str


@dataclass(frozen=True, slots=True)
class CardVisibilityEvent:
    """Persist one production operation that set a card's visibility."""

    node_id: str
    event: str
    requested_visible: bool
    actual_visible: bool | None
    base_card_visible: bool | None


@dataclass(frozen=True, slots=True)
class CardLifecycleObservation:
    """Persist the final production card registry and masonry state for one node."""

    registered: bool
    widget_type: str
    valid: bool
    parent_type: str
    in_masonry: bool
    masonry_index: int | None
    visible: bool
    hidden: bool
    base_card_visible: bool | None
    has_title_controls: bool | None
    geometry: tuple[int, int, int, int] | None
    registered_field_keys: tuple[str, ...]
    visibility_events: tuple[CardVisibilityEvent, ...]


@dataclass(frozen=True, slots=True)
class NodeObservation:
    """Persist production-owned behavior, factories, outcome, and card state."""

    node_id: str
    class_type: str
    title: str
    behavior_present: bool
    decision_present: bool
    decision_visible: bool | None
    decision_enabled: bool | None
    decision_reason: str
    decision_show_enabled_switch: bool | None
    field_specs: tuple[FieldSpecObservation, ...]
    factory_observations: tuple[FieldFactoryObservation, ...]
    build_outcomes: tuple[NodeCardBuildOutcome, ...]
    card: CardLifecycleObservation


@dataclass(frozen=True, slots=True)
class WorkflowAuditResult:
    """Persist one workflow's complete passive production observation."""

    workflow: str
    title: str
    category: str
    source_node_count: int
    source_projected_node_count: int
    converted_node_count: int
    behavior_node_count: int
    build_outcome_count: int
    built_card_count: int
    final_visible_card_count: int
    registered_field_widget_count: int
    elapsed_ms: float
    screenshot: str
    nodes: tuple[NodeObservation, ...]
    runtime_logs: tuple[RuntimeLogObservation, ...]
    findings: tuple[AuditFinding, ...]

    @property
    def succeeded(self) -> bool:
        """Return whether no production failure was observed."""

        return not self.findings


@dataclass(frozen=True, slots=True)
class BundledWorkflowAuditReport:
    """Persist aggregate accounting for one complete observational corpus run."""

    schema_version: int
    audit_mode: str
    qt_platform: str
    template_root: str
    catalog_fingerprint: str
    workflow_count: int
    succeeded_workflow_count: int
    failed_workflow_count: int
    source_node_count: int
    source_projected_node_count: int
    converted_node_count: int
    build_outcome_count: int
    built_card_count: int
    final_visible_card_count: int
    registered_field_widget_count: int
    factory_observation_count: int
    factory_result_counts: Mapping[str, int]
    build_outcome_counts: Mapping[str, int]
    finding_count: int
    finding_counts_by_code: Mapping[str, int]
    elapsed_ms: float
    results: tuple[WorkflowAuditResult, ...]
