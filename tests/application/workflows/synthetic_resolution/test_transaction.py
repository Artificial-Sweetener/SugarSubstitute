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

"""Verify guarded, atomic synthetic canvas dimension projection."""

from __future__ import annotations

from typing import Any, cast

import pytest

from substitute.application.workflows.synthetic_canvas_resolution_role_service import (
    SyntheticCanvasResolutionRole,
    SyntheticCanvasResolutionRoleService,
)
from substitute.application.workflows.synthetic_canvas_resolution_transaction_service import (
    SyntheticCanvasResolutionStaleError,
    SyntheticCanvasResolutionTransactionService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import (
    CanvasDimensionAuthority,
    CanvasDimensions,
    CubeState,
    WorkflowState,
)


class _RoleResolver:
    """Return a test-controlled current semantic role."""

    def __init__(self, current: SyntheticCanvasResolutionRole | None) -> None:
        """Store the role returned by every node lookup."""

        self.current = current

    def resolve_for_node(
        self, **_kwargs: object
    ) -> SyntheticCanvasResolutionRole | None:
        """Return the configured current role."""

        return self.current


class _RejectingInputs(dict[str, object]):
    """Reject one target assignment to exercise graph rollback."""

    def __setitem__(self, key: str, value: object) -> None:
        """Reject changing height to its requested test value."""

        if key == "height" and value == 900:
            raise RuntimeError("rejected test assignment")
        super().__setitem__(key, value)


def test_projects_every_authority_node_as_one_graph_mutation() -> None:
    """Converged dimension roots should remain identical after one commit."""

    workflow = _workflow(
        first={"width": 960, "height": 1344},
        second={"target_width": 960, "target_height": 1344},
    )
    expected = _role(
        node_names=("first", "second"),
        field_pairs=(("width", "height"), ("target_width", "target_height")),
    )
    graph_sections = WorkflowGraphSectionService()
    transaction = SyntheticCanvasResolutionTransactionService(
        roles=cast(SyntheticCanvasResolutionRoleService, _RoleResolver(expected)),
        graph_sections=graph_sections,
    )

    transaction.project(
        workflow,
        expected=expected,
        dimensions=CanvasDimensions(1216, 832),
    )

    graph = graph_sections.graph(workflow, "Region")
    assert graph is not None
    nodes = cast(dict[str, dict[str, object]], graph["nodes"])
    assert nodes["first"]["inputs"] == {"width": 1216, "height": 832}
    assert nodes["second"]["inputs"] == {
        "target_width": 1216,
        "target_height": 832,
    }
    assert workflow.cubes["Region"].dirty


def test_rejects_role_when_graph_authority_changed_after_dialog_opened() -> None:
    """A changed structural fingerprint should fail before graph mutation."""

    workflow = _workflow(first={"width": 960, "height": 1344})
    expected = _role(node_names=("first",), field_pairs=(("width", "height"),))
    changed = _role(
        node_names=("first",),
        field_pairs=(("width", "height"),),
        structural_fingerprint="new-structure",
    )
    transaction = SyntheticCanvasResolutionTransactionService(
        roles=cast(SyntheticCanvasResolutionRoleService, _RoleResolver(changed)),
        graph_sections=WorkflowGraphSectionService(),
    )

    with pytest.raises(SyntheticCanvasResolutionStaleError):
        transaction.project(
            workflow,
            expected=expected,
            dimensions=CanvasDimensions(512, 512),
        )

    assert not workflow.cubes["Region"].dirty


def test_atomic_graph_mutation_rolls_back_earlier_fields_on_assignment_failure() -> (
    None
):
    """A failed later field should restore all earlier values and dirty state."""

    workflow = _workflow(
        first={"width": 960, "height": 1344},
        second=_RejectingInputs(width=960, height=1344),
    )
    service = WorkflowGraphSectionService()

    with pytest.raises(RuntimeError, match="rejected test assignment"):
        service.set_input_values_atomic(
            workflow,
            section_key="Region",
            values=(
                ("first", "width", 1200),
                ("second", "height", 900),
            ),
        )

    graph = service.graph(workflow, "Region")
    assert graph is not None
    nodes = cast(dict[str, dict[str, object]], graph["nodes"])
    assert cast(dict[str, object], nodes["first"]["inputs"])["width"] == 960
    assert cast(dict[str, object], nodes["second"]["inputs"])["height"] == 1344
    assert not workflow.cubes["Region"].dirty


def test_dimension_authority_rejects_misaligned_node_and_field_pair_counts() -> None:
    """The authority invariant should prevent partial multi-node projection."""

    with pytest.raises(ValueError, match="nodes and field pairs"):
        CanvasDimensionAuthority(
            dimensions=CanvasDimensions(960, 1344),
            node_names=("first", "second"),
            field_pairs=(("width", "height"),),
            convergence_node_names=("sampler",),
            structural_fingerprint="structure",
            dimension_fingerprint="dimensions",
        )


def _role(
    *,
    node_names: tuple[str, ...],
    field_pairs: tuple[tuple[str, str], ...],
    structural_fingerprint: str = "structure",
) -> SyntheticCanvasResolutionRole:
    """Build one immutable synthetic authority snapshot."""

    return SyntheticCanvasResolutionRole(
        section_key="Region",
        surface_key="@synthetic/region",
        authority=CanvasDimensionAuthority(
            dimensions=CanvasDimensions(960, 1344),
            node_names=node_names,
            field_pairs=field_pairs,
            convergence_node_names=("sampler",),
            structural_fingerprint=structural_fingerprint,
            dimension_fingerprint="960x1344",
        ),
    )


def _workflow(**node_inputs: dict[str, object]) -> WorkflowState:
    """Build one cube workflow around the supplied node input mappings."""

    graph = {
        "nodes": {
            node_name: {"class_type": "TestNode", "inputs": inputs}
            for node_name, inputs in node_inputs.items()
        }
    }
    cube = CubeState(
        cube_id="test.region",
        version="1.0",
        alias="Region",
        original_cube=cast(Any, graph),
        buffer=cast(Any, graph),
    )
    return WorkflowState(cubes={"Region": cube}, stack_order=["Region"])
