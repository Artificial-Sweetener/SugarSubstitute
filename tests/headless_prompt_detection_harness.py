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

"""Audit prompt-card detection against genuine managed Comfy templates."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from substitute.application.node_behavior import NodeBehaviorService
from substitute.domain.comfy_workflow import ComfyWorkflowConverter, DirectWorkflowState
from substitute.domain.node_behavior import PromptRole
from substitute.domain.node_behavior.prompt_graph import PromptEvidence
from substitute.infrastructure.comfy.workflow_document_repository import (
    ComfyWorkflowDocumentRepository,
)
from tests.prompt_detection_fixture_catalog import (
    ExpectedPromptField,
    PromptDetectionFixture,
    managed_prompt_detection_fixtures,
)
from tests.recorded_node_definition_gateway import RecordedNodeDefinitionGateway

_SECTION = "direct"


@dataclass(frozen=True, slots=True, order=True)
class DetectedPromptField:
    """Describe one prompt field observed through production behavior resolution."""

    node_name: str
    field_key: str
    role: PromptRole
    evidence: tuple[PromptEvidence, ...]


@dataclass(frozen=True, slots=True)
class PromptFixtureReport:
    """Summarize one real-template detection audit."""

    name: str
    workflow: str
    detected: tuple[DetectedPromptField, ...]
    missing: tuple[ExpectedPromptField, ...]
    unexpected: tuple[DetectedPromptField, ...]
    ambiguities: tuple[dict[str, object], ...]
    missing_standard_fields: tuple[tuple[str, str], ...] = ()
    missing_ambiguities: tuple[tuple[str, tuple[str, ...]], ...] = ()
    unexpected_ambiguities: tuple[tuple[str, tuple[str, ...]], ...] = ()
    card_order: tuple[str, ...] = ()
    context_anchors: tuple[str, ...] = ()
    opening_mismatch: tuple[str, ...] = ()
    context_anchor_mismatch: tuple[str, ...] = ()
    duplicate_order_nodes: tuple[str, ...] = ()
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether expected detection is exact and failure-free."""

        return (
            self.error is None
            and not self.missing
            and not self.unexpected
            and not self.missing_standard_fields
            and not self.missing_ambiguities
            and not self.unexpected_ambiguities
            and not self.opening_mismatch
            and not self.context_anchor_mismatch
            and not self.duplicate_order_nodes
        )


@dataclass(frozen=True, slots=True)
class PromptDetectionCorpusReport:
    """Summarize all real-template prompt detection fixtures."""

    fixtures: tuple[PromptFixtureReport, ...]

    @property
    def succeeded(self) -> bool:
        """Return whether every fixture has exact detection and no false positives."""

        return all(fixture.succeeded for fixture in self.fixtures)


class HeadlessPromptDetectionHarness:
    """Run real templates through conversion and production behavior resolution."""

    def run(
        self,
        fixtures: Sequence[PromptDetectionFixture],
    ) -> PromptDetectionCorpusReport:
        """Return a complete corpus report while retaining per-fixture failures."""

        return PromptDetectionCorpusReport(
            fixtures=tuple(self._run_fixture(fixture) for fixture in fixtures)
        )

    def _run_fixture(
        self,
        fixture: PromptDetectionFixture,
    ) -> PromptFixtureReport:
        """Run one workflow through the production non-Qt behavior path."""

        try:
            workflow = ComfyWorkflowDocumentRepository().load(fixture.path)
            graph = ComfyWorkflowConverter().convert(
                workflow,
                node_definitions=fixture.node_definitions,
            )
            state = DirectWorkflowState(
                source_path=fixture.path,
                source_workflow=workflow,
                buffer=graph,
            )
            snapshot = NodeBehaviorService(
                node_definition_gateway=RecordedNodeDefinitionGateway(
                    fixture.node_definitions
                )
            ).build_snapshot(
                cube_states={_SECTION: state},
                stack_order=[_SECTION],
            )
            detection_result = snapshot.prompt_detection_results_by_alias[_SECTION]
            evidence_by_field = {
                (detection.locator.node_name, detection.locator.field_key): (
                    detection.evidence
                )
                for detection in detection_result.detections
            }
            detected = tuple(
                sorted(
                    DetectedPromptField(
                        node_name=node_name,
                        field_key=field_key,
                        role=field.prompt.role,
                        evidence=evidence_by_field.get((node_name, field_key), ()),
                    )
                    for node_name, behavior in snapshot.resolved_nodes_by_alias[
                        _SECTION
                    ].items()
                    for field_key, field in behavior.fields.items()
                    if field.prompt is not None
                )
            )
            expected_keys = {
                (item.node_name, item.field_key, item.role)
                for item in fixture.expected_prompts
            }
            detected_keys = {
                (item.node_name, item.field_key, item.role) for item in detected
            }
            missing = tuple(
                item
                for item in fixture.expected_prompts
                if (item.node_name, item.field_key, item.role) not in detected_keys
            )
            unexpected = tuple(
                item
                for item in detected
                if (item.node_name, item.field_key, item.role) not in expected_keys
            )
            ambiguities: tuple[dict[str, object], ...] = tuple(
                {
                    "reason": ambiguity.reason.value,
                    "detail": ambiguity.detail,
                    "fields": [
                        f"{locator.node_name}.{locator.field_key}"
                        for locator in ambiguity.locators
                    ],
                }
                for ambiguity in detection_result.ambiguities
            )
            observed_ambiguities = tuple(
                (
                    ambiguity.reason.value,
                    tuple(
                        f"{locator.node_name}.{locator.field_key}"
                        for locator in ambiguity.locators
                    ),
                )
                for ambiguity in detection_result.ambiguities
            )
            standard_fields = {
                (node_name, field_key)
                for node_name, behavior in snapshot.resolved_nodes_by_alias[
                    _SECTION
                ].items()
                for field_key, field in behavior.fields.items()
                if field.prompt is None
            }
            card_order = snapshot.card_order_by_alias[_SECTION]
            context_anchors = tuple(
                context.anchor_node_name
                for context in snapshot.prompt_contexts_by_alias[_SECTION]
            )
            expected_opening = fixture.expected_opening_cards
            opening_mismatch = (
                card_order[: len(expected_opening)]
                if expected_opening
                and card_order[: len(expected_opening)] != expected_opening
                else ()
            )
            context_anchor_mismatch = (
                context_anchors
                if context_anchors != fixture.expected_context_anchors
                else ()
            )
            duplicate_order_nodes = tuple(
                node_name
                for node_name in dict.fromkeys(card_order)
                if card_order.count(node_name) > 1
            )
            return PromptFixtureReport(
                name=fixture.name,
                workflow=str(fixture.path),
                detected=detected,
                missing=missing,
                unexpected=unexpected,
                ambiguities=ambiguities,
                missing_standard_fields=tuple(
                    field
                    for field in fixture.expected_standard_fields
                    if field not in standard_fields
                ),
                missing_ambiguities=tuple(
                    expected
                    for expected in fixture.expected_ambiguities
                    if expected not in observed_ambiguities
                ),
                unexpected_ambiguities=tuple(
                    observed
                    for observed in observed_ambiguities
                    if observed not in fixture.expected_ambiguities
                ),
                card_order=card_order,
                context_anchors=context_anchors,
                opening_mismatch=opening_mismatch,
                context_anchor_mismatch=context_anchor_mismatch,
                duplicate_order_nodes=duplicate_order_nodes,
            )
        except (OSError, RuntimeError, TypeError, ValueError, KeyError) as error:
            return PromptFixtureReport(
                name=fixture.name,
                workflow=str(fixture.path),
                detected=(),
                missing=fixture.expected_prompts,
                unexpected=(),
                ambiguities=(),
                missing_standard_fields=fixture.expected_standard_fields,
                missing_ambiguities=fixture.expected_ambiguities,
                error=f"{type(error).__name__}: {error}",
            )


def main() -> int:
    """Run the managed corpus from PowerShell and optionally persist JSON."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = HeadlessPromptDetectionHarness().run(
        managed_prompt_detection_fixtures(args.repository_root)
    )
    rendered = json.dumps(asdict(report), indent=2, sort_keys=True)
    if args.report is not None:
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if report.succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DetectedPromptField",
    "HeadlessPromptDetectionHarness",
    "PromptDetectionCorpusReport",
    "PromptFixtureReport",
]
