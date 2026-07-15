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

"""Contract tests for workflow-level link reconciliation orchestration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Mapping, cast

from substitute.application.workflows import WorkflowLinkReconciliationService
from substitute.domain.links import NodeLinkEndpoint, NodeLinkEndpointIndex
from substitute.domain.links.prompt_endpoints import PromptEndpointIndex


class _PromptEndpointProvider:
    """Return no prompt endpoints for whole-node focused service tests."""

    def build_prompt_endpoint_index(
        self,
        cube_states: Mapping[str, object],
        stack_order: list[str],
    ) -> PromptEndpointIndex:
        """Return an empty prompt endpoint index."""

        return PromptEndpointIndex()


class _NodeLinkEndpointProvider:
    """Build deterministic Vectorscope endpoints for service tests."""

    _editable_keys = (
        "alt",
        "brightness",
        "contrast",
        "saturation",
        "r",
        "g",
        "b",
        "method",
        "scaling",
    )

    def build_node_link_endpoint_index(
        self,
        cube_states: Mapping[str, object],
        stack_order: list[str],
    ) -> NodeLinkEndpointIndex:
        """Return Vectorscope endpoints from minimal cube-state doubles."""

        endpoints: list[NodeLinkEndpoint] = []
        for cube_alias in stack_order:
            cube_state = cube_states.get(cube_alias)
            buffer = getattr(cube_state, "buffer", {})
            nodes = buffer.get("nodes", {}) if isinstance(buffer, dict) else {}
            if not isinstance(nodes, Mapping):
                continue
            node = nodes.get("vectorscopecc")
            if not isinstance(node, Mapping):
                continue
            endpoints.append(
                NodeLinkEndpoint(
                    cube_alias=cube_alias,
                    node_name="vectorscopecc",
                    class_type=str(node.get("class_type", "")),
                    family="vectorscopecc",
                    editable_value_keys=self._editable_keys,
                    graph_signature=self._graph_signature(node),
                )
            )
        return NodeLinkEndpointIndex.from_endpoints(endpoints)

    @staticmethod
    def _graph_signature(
        node: Mapping[str, object],
    ) -> tuple[tuple[str, object], ...]:
        """Return connection-shaped inputs that must match for link eligibility."""

        inputs = node.get("inputs", {})
        if not isinstance(inputs, Mapping):
            return ()
        signature: list[tuple[str, object]] = []
        for key, value in inputs.items():
            if (
                isinstance(key, str)
                and isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], str)
                and isinstance(value[1], int)
            ):
                signature.append((key, (value[0], value[1])))
        return tuple(sorted(signature))


class _CombinedEndpointProvider:
    """Return both endpoint indexes from one counted provider call."""

    def __init__(self) -> None:
        """Initialize call counters for cache assertions."""

        self.combined_calls = 0
        self.prompt_calls = 0
        self.node_calls = 0

    def build_link_endpoint_indexes(
        self,
        cube_states: Mapping[str, object],
        stack_order: list[str],
    ) -> tuple[PromptEndpointIndex, NodeLinkEndpointIndex]:
        """Return empty indexes while counting combined calls."""

        self.combined_calls += 1
        return PromptEndpointIndex(), NodeLinkEndpointIndex()

    def build_prompt_endpoint_index(
        self,
        cube_states: Mapping[str, object],
        stack_order: list[str],
    ) -> PromptEndpointIndex:
        """Record unexpected direct prompt-index calls."""

        self.prompt_calls += 1
        return PromptEndpointIndex()

    def build_node_link_endpoint_index(
        self,
        cube_states: Mapping[str, object],
        stack_order: list[str],
    ) -> NodeLinkEndpointIndex:
        """Record unexpected direct node-link-index calls."""

        self.node_calls += 1
        return NodeLinkEndpointIndex()


def _service() -> WorkflowLinkReconciliationService:
    """Return workflow reconciliation with deterministic endpoint providers."""

    return WorkflowLinkReconciliationService(
        prompt_endpoint_provider=_PromptEndpointProvider(),
        node_link_endpoint_provider=_NodeLinkEndpointProvider(),
    )


def _cube_state(buffer: dict[str, object]) -> SimpleNamespace:
    """Build a minimal cube-state double with a mutable workflow buffer."""

    return SimpleNamespace(buffer=buffer)


def _vectorscope_node(
    *,
    brightness: float,
    from_cube: str | None | object = ...,
    from_node: str | None = None,
) -> dict[str, object]:
    """Build one Vectorscope node payload with optional link metadata."""

    node: dict[str, object] = {
        "class_type": "VectorscopeCC",
        "inputs": {"model": ["provider", 0], "brightness": brightness},
    }
    if from_cube is not ...:
        node["node_link"] = {"from_cube": from_cube, "from_node": from_node}
    return node


def _node_link_payload(node: dict[str, object]) -> dict[str, object]:
    """Return one node's serialized link payload."""

    return cast(dict[str, object], node["node_link"])


def test_reconcile_transition_reuses_combined_endpoint_indexes_per_stack() -> None:
    """Reconciliation should not rebuild prompt and node endpoint indexes separately."""

    provider = _CombinedEndpointProvider()
    service = WorkflowLinkReconciliationService(
        prompt_endpoint_provider=provider,
        node_link_endpoint_provider=provider,
    )
    current = {
        "A": _cube_state({"nodes": {}}),
        "B": _cube_state({"nodes": {}}),
    }

    service.reconcile_transition(
        previous_cube_states=None,
        previous_stack_order=None,
        current_cube_states=current,
        current_stack_order=["A", "B"],
    )

    assert provider.combined_calls == 1
    assert provider.prompt_calls == 0
    assert provider.node_calls == 0


def test_reconcile_transition_links_new_vectorscope_cube_to_earlier_batch_peer() -> (
    None
):
    """Batch-final reconciliation should default-link compatible downstream nodes."""

    service = _service()
    previous: dict[str, object] = {}
    current = {
        "A": _cube_state(
            {"nodes": {"vectorscopecc": _vectorscope_node(brightness=0.25)}}
        ),
        "B": _cube_state(
            {"nodes": {"vectorscopecc": _vectorscope_node(brightness=0.75)}}
        ),
    }

    service.reconcile_transition(
        previous_cube_states=previous,
        previous_stack_order=[],
        current_cube_states=current,
        current_stack_order=["A", "B"],
    )
    service.sanitize_current_state(cube_states=current, stack_order=["A", "B"])

    linked_node = current["B"].buffer["nodes"]["vectorscopecc"]
    assert _node_link_payload(linked_node) == {
        "from_cube": "A",
        "from_node": "vectorscopecc",
    }


def test_reconcile_transition_preserves_explicit_independent_vectorscope_node() -> None:
    """Explicit independent metadata should block batch-final default linking."""

    service = _service()
    current = {
        "A": _cube_state(
            {"nodes": {"vectorscopecc": _vectorscope_node(brightness=0.25)}}
        ),
        "B": _cube_state(
            {
                "nodes": {
                    "vectorscopecc": _vectorscope_node(
                        brightness=0.75,
                        from_cube=None,
                        from_node=None,
                    )
                }
            }
        ),
    }

    service.reconcile_transition(
        previous_cube_states={},
        previous_stack_order=[],
        current_cube_states=current,
        current_stack_order=["A", "B"],
    )
    service.sanitize_current_state(cube_states=current, stack_order=["A", "B"])

    linked_node = current["B"].buffer["nodes"]["vectorscopecc"]
    assert _node_link_payload(linked_node) == {
        "from_cube": None,
        "from_node": None,
    }
