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

"""Audit source-to-production direct-workflow conversion identity."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.domain.comfy_workflow import DirectWorkflowState
from tests.qualification.comfy.bundled_workflows.catalog import (
    BundledWorkflowCatalogEntry,
    SourceWorkflowInventory,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.models import (
    AuditFinding,
)


def converted_nodes(direct: DirectWorkflowState) -> dict[str, Mapping[str, object]]:
    """Return typed converted nodes from one direct workflow buffer."""

    raw_nodes = direct.buffer.get("nodes")
    if not isinstance(raw_nodes, Mapping):
        raise AssertionError("converted direct workflow has no node mapping")
    return {
        str(node_id): node
        for node_id, node in raw_nodes.items()
        if isinstance(node, Mapping)
    }


def conversion_findings(
    entry: BundledWorkflowCatalogEntry,
    inventory: SourceWorkflowInventory,
    converted: Mapping[str, Mapping[str, object]],
) -> tuple[AuditFinding, ...]:
    """Report source-to-production conversion identity contradictions only."""

    expected = {node.node_id: node for node in inventory.projected_nodes}
    findings: list[AuditFinding] = []
    for node_id in sorted(set(expected) - set(converted)):
        findings.append(
            _finding(
                entry,
                code="conversion_missing_node",
                message="A source-projectable node is absent after conversion.",
                node_id=node_id,
                class_type=expected[node_id].class_type,
            )
        )
    for node_id in sorted(set(converted) - set(expected)):
        findings.append(
            _finding(
                entry,
                code="conversion_unexpected_node",
                message="Conversion produced a node absent from source expansion.",
                node_id=node_id,
                class_type=str(converted[node_id].get("class_type", "")),
            )
        )
    for node_id in sorted(set(expected) & set(converted)):
        actual_class = str(converted[node_id].get("class_type", ""))
        if actual_class != expected[node_id].class_type:
            findings.append(
                _finding(
                    entry,
                    code="conversion_class_mismatch",
                    message=(
                        f"Source class {expected[node_id].class_type!r} became "
                        f"{actual_class!r}."
                    ),
                    node_id=node_id,
                    class_type=actual_class,
                )
            )
    return tuple(findings)


def _finding(
    entry: BundledWorkflowCatalogEntry,
    *,
    code: str,
    message: str,
    node_id: str,
    class_type: str,
) -> AuditFinding:
    """Build one conversion-scoped observation finding."""

    return AuditFinding(
        workflow=entry.name,
        category=entry.category,
        code=code,
        stage="conversion",
        message=message,
        node_id=node_id,
        class_type=class_type,
    )
