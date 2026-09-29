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

"""Tests for authoritative workflow node-definition assessment."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from substitute.application.comfy_nodepacks.workflow_node_definition_assessment import (
    WorkflowNodeDefinitionAssessmentService,
    WorkflowNodeDefinitionAssessmentUnavailable,
)
from substitute.application.ports import NodeDefinitionHydrationResult


class _Gateway:
    """Hydrate configured class definitions while recording the request."""

    def __init__(self, available: set[str]) -> None:
        """Store class names that should expose live definitions."""

        self.available = available
        self.requests: list[tuple[str, ...]] = []

    def ensure_node_definitions(
        self,
        node_classes: Iterable[str],
    ) -> NodeDefinitionHydrationResult:
        """Return availability for the requested classes."""

        requested = tuple(node_classes)
        self.requests.append(requested)
        return NodeDefinitionHydrationResult(
            requested=requested,
            available=tuple(item for item in requested if item in self.available),
            unavailable=tuple(item for item in requested if item not in self.available),
        )

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return a minimal definition for configured classes."""

        return {node_class: {"input": {}}} if node_class in self.available else {}

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the same deterministic live payload."""

        return self.get_node_definition(node_class)


class _NonHydratingGateway:
    """Expose cached lookup without claiming authoritative refresh support."""

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return no cached definition."""

        _ = node_class
        return {}

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return no synchronous definition."""

        _ = node_class
        return {}


def _workflow() -> dict[str, object]:
    """Build a mixed ordinary workflow with repeated missing classes."""

    return {
        "nodes": [
            {"id": 1, "type": "Healthy", "title": "Healthy"},
            {"id": 2, "type": "Missing", "title": "Missing one"},
            {"id": 3, "type": "Missing", "title": "Missing two"},
        ],
        "links": [],
    }


def test_assesses_all_nodes_after_one_deduplicated_hydration() -> None:
    """The live boundary should hydrate classes once and retain node instances."""

    gateway = _Gateway({"Healthy"})

    assessment = WorkflowNodeDefinitionAssessmentService(gateway).assess(_workflow())

    assert gateway.requests == [("Healthy", "Missing")]
    assert [node.title for node in assessment.available] == ["Healthy"]
    assert [node.title for node in assessment.missing] == [
        "Missing one",
        "Missing two",
    ]
    assert assessment.missing_class_types == ("Missing",)


def test_refuses_to_guess_from_a_non_hydrating_cache() -> None:
    """A stale cache miss must not be presented as evidence of a missing nodepack."""

    with pytest.raises(WorkflowNodeDefinitionAssessmentUnavailable):
        WorkflowNodeDefinitionAssessmentService(_NonHydratingGateway()).assess(
            _workflow()
        )
