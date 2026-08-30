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

"""Aggregate and persist bundled-workflow audit evidence."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from tests.qualification.comfy.bundled_workflows.catalog import BundledWorkflowCatalog
from tests.qualification.comfy.bundled_workflows.rendering_audit.models import (
    BundledWorkflowAuditReport,
    WorkflowAuditResult,
)


def build_report(
    catalog: BundledWorkflowCatalog,
    results: tuple[WorkflowAuditResult, ...],
    *,
    qt_platform: str,
    elapsed_ms: float,
) -> BundledWorkflowAuditReport:
    """Aggregate accounting without reclassifying production outcomes."""

    findings = [finding for result in results for finding in result.findings]
    factory_observations = [
        observation
        for result in results
        for node in result.nodes
        for observation in node.factory_observations
    ]
    build_outcomes = [
        outcome
        for result in results
        for node in result.nodes
        for outcome in node.build_outcomes
    ]
    return BundledWorkflowAuditReport(
        schema_version=1,
        audit_mode="passive_production_observation",
        qt_platform=qt_platform,
        template_root=str(catalog.template_root),
        catalog_fingerprint=catalog.fingerprint,
        workflow_count=len(results),
        succeeded_workflow_count=sum(result.succeeded for result in results),
        failed_workflow_count=sum(not result.succeeded for result in results),
        source_node_count=sum(result.source_node_count for result in results),
        source_projected_node_count=sum(
            result.source_projected_node_count for result in results
        ),
        converted_node_count=sum(result.converted_node_count for result in results),
        build_outcome_count=sum(result.build_outcome_count for result in results),
        built_card_count=sum(result.built_card_count for result in results),
        final_visible_card_count=sum(
            result.final_visible_card_count for result in results
        ),
        registered_field_widget_count=sum(
            result.registered_field_widget_count for result in results
        ),
        factory_observation_count=len(factory_observations),
        factory_result_counts=dict(
            sorted(Counter(item.result for item in factory_observations).items())
        ),
        build_outcome_counts=dict(
            sorted(Counter(item.kind for item in build_outcomes).items())
        ),
        finding_count=len(findings),
        finding_counts_by_code=dict(
            sorted(Counter(item.code for item in findings).items())
        ),
        elapsed_ms=elapsed_ms,
        results=results,
    )


def write_report(path: Path, report: BundledWorkflowAuditReport) -> None:
    """Persist one complete observational JSON report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True),
        encoding="utf-8",
    )
