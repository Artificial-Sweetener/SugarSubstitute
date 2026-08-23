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

"""Verify direct-workflow generation preflight."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from substitute.application.direct_workflows import DirectWorkflowGenerationPlanService
from substitute.application.ports import NodeDefinitionHydrationResult
from substitute.domain.comfy_workflow import (
    ComfyApiGraphBuildError,
    DirectWorkflowState,
)


class _Hydrator:
    """Record requested backend classes and report them unavailable."""

    def __init__(self) -> None:
        self.requested: tuple[str, ...] = ()

    def ensure_node_definitions(
        self,
        node_classes: Iterable[str],
    ) -> NodeDefinitionHydrationResult:
        """Record and reject every requested class."""
        self.requested = tuple(node_classes)
        return NodeDefinitionHydrationResult(
            requested=self.requested,
            available=(),
            unavailable=self.requested,
        )


def test_execution_preflight_checks_only_active_backend_classes() -> None:
    """Ignore frontend proxies and authored bypass nodes during hydration."""
    hydrator = _Hydrator()
    document = DirectWorkflowState(
        source_path=Path("workflow.json"),
        source_workflow={"nodes": [], "links": []},
        buffer={
            "nodes": {
                "1": {
                    "class_type": "PrimitiveNode",
                    "inputs": {"amount": 2},
                    "_workflow": {
                        "execution_role": "value_proxy",
                        "value_field": "amount",
                    },
                },
                "2": {
                    "class_type": "MissingCustomNode",
                    "inputs": {"amount": ["1", 0]},
                    "_workflow": {"execution_role": "executable"},
                },
                "3": {
                    "class_type": "BypassedOptionalNode",
                    "inputs": {},
                    "mode": 4,
                    "_workflow": {"execution_role": "executable"},
                },
            }
        },
    )
    service = DirectWorkflowGenerationPlanService(node_definition_hydrator=hydrator)

    with pytest.raises(ComfyApiGraphBuildError, match="MissingCustomNode"):
        service.build(document)

    assert hydrator.requested == ("MissingCustomNode",)
