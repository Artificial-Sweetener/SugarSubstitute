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

"""Plan authored and synthetic Input canvas surfaces from shared graph semantics."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.workflows.canvas_dimension_authority_service import (
    CanvasDimensionAuthorityService,
)
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
    declared_input_type,
)
from substitute.application.workflows.workflow_graph_topology import (
    WorkflowGraphEdge,
    WorkflowGraphTopology,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
    node_class_type,
)
from substitute.domain.workflow import InputAssetEndpoint, InputAssetRole
from substitute.domain.workflow.input_canvas_plan import (
    CanvasDimensionResolutionKind,
    InputCanvasMaskBinding,
    InputCanvasPlan,
    InputCanvasPlanRejection,
    InputCanvasSurface,
    InputCanvasSurfaceKind,
)

_SYNTHETIC_SURFACE_PREFIX = "@synthetic"


class InputCanvasPlanService:
    """Own the single graph-derived plan consumed by every Input canvas path."""

    def __init__(
        self,
        *,
        node_definition_service: WorkflowNodeDefinitionService,
        endpoint_service: InputAssetEndpointService,
        dimension_authority_service: CanvasDimensionAuthorityService | None = None,
    ) -> None:
        """Capture focused semantic collaborators."""

        self._node_definition_service = node_definition_service
        self._endpoint_service = endpoint_service
        self._dimension_authority_service = (
            dimension_authority_service or CanvasDimensionAuthorityService()
        )

    def build_plan(
        self,
        section_key: str,
        graph: Mapping[str, object],
        *,
        node_definitions: Mapping[str, Mapping[str, object]] | None = None,
    ) -> InputCanvasPlan:
        """Return all safe surfaces and mask bindings for one isolated graph section."""

        definitions = self._node_definition_service.definitions_for_graph(
            graph,
            node_definitions,
        )
        topology = WorkflowGraphTopology(graph, definitions)
        endpoint_index = self._endpoint_service.build_index(
            section_key,
            graph,
            node_definitions=definitions,
        )
        authored_surfaces = {
            endpoint.node_name: InputCanvasSurface(
                section_key=section_key,
                surface_key=endpoint.node_name,
                kind=InputCanvasSurfaceKind.AUTHORED_IMAGE,
                image_endpoint=endpoint,
            )
            for endpoint in endpoint_index.image_endpoints
        }
        authored_candidates = self._authored_binding_candidates(
            endpoints=endpoint_index.endpoints,
            surfaces=authored_surfaces,
            topology=topology,
            definitions=definitions,
        )
        authored_bindings, ambiguous_candidates = _unique_authored_bindings(
            authored_candidates
        )
        bound_mask_nodes = {
            binding.mask_endpoint.node_name for binding in authored_bindings
        }

        synthetic_surfaces: dict[str, InputCanvasSurface] = {}
        synthetic_bindings: list[InputCanvasMaskBinding] = []
        rejections: list[InputCanvasPlanRejection] = []
        for mask_endpoint in endpoint_index.mask_endpoints:
            if mask_endpoint.node_name in bound_mask_nodes:
                continue
            ambiguous = ambiguous_candidates.get(mask_endpoint.node_name)
            if ambiguous is not None:
                rejections.append(
                    InputCanvasPlanRejection(
                        mask_endpoint=mask_endpoint,
                        kind=CanvasDimensionResolutionKind.AMBIGUOUS,
                        reason="multiple_authored_image_contexts",
                        candidate_node_names=tuple(
                            dict.fromkeys(
                                candidate.surface.surface_key for candidate in ambiguous
                            )
                        ),
                    )
                )
                continue
            resolution = self._dimension_authority_service.resolve(
                mask_endpoint,
                topology,
            )
            if (
                resolution.kind is not CanvasDimensionResolutionKind.RESOLVED
                or resolution.authority is None
            ):
                rejections.append(
                    InputCanvasPlanRejection(
                        mask_endpoint=mask_endpoint,
                        kind=resolution.kind,
                        reason=resolution.reason,
                        candidate_node_names=resolution.candidate_node_names,
                    )
                )
                continue
            authority = resolution.authority
            surface_key = f"{_SYNTHETIC_SURFACE_PREFIX}/{authority.fingerprint[:16]}"
            surface = synthetic_surfaces.get(surface_key)
            if surface is None:
                surface = InputCanvasSurface(
                    section_key=section_key,
                    surface_key=surface_key,
                    kind=InputCanvasSurfaceKind.SYNTHETIC,
                    dimension_authority=authority,
                )
                synthetic_surfaces[surface_key] = surface
            synthetic_bindings.append(
                InputCanvasMaskBinding(
                    surface=surface,
                    mask_endpoint=mask_endpoint,
                    consumer_node_name=_mask_consumer_identity(
                        topology,
                        mask_endpoint,
                        authority.convergence_node_names,
                    ),
                )
            )

        return InputCanvasPlan(
            section_key=section_key,
            surfaces=tuple(authored_surfaces.values())
            + tuple(synthetic_surfaces.values()),
            mask_bindings=authored_bindings + tuple(synthetic_bindings),
            rejections=tuple(rejections),
        )

    @staticmethod
    def _authored_binding_candidates(
        *,
        endpoints: tuple[InputAssetEndpoint, ...],
        surfaces: Mapping[str, InputCanvasSurface],
        topology: WorkflowGraphTopology,
        definitions: Mapping[str, Mapping[str, object]],
    ) -> tuple[InputCanvasMaskBinding, ...]:
        """Return exact same-consumer image/mask candidates before ambiguity policy."""

        endpoint_by_socket = {
            (endpoint.node_name, endpoint.output_index): endpoint
            for endpoint in endpoints
        }
        per_consumer: dict[
            str,
            list[tuple[WorkflowGraphEdge, InputAssetEndpoint]],
        ] = {}
        for edge in topology.edges:
            endpoint = endpoint_by_socket.get((edge.provider_name, edge.output_index))
            if endpoint is None or not _consumer_accepts_endpoint(
                edge,
                endpoint,
                topology,
                definitions,
            ):
                continue
            per_consumer.setdefault(edge.consumer_name, []).append((edge, endpoint))

        candidates: list[InputCanvasMaskBinding] = []
        for consumer_name, connected in per_consumer.items():
            images = tuple(
                endpoint
                for _edge, endpoint in connected
                if endpoint.role is InputAssetRole.IMAGE
            )
            masks = tuple(
                endpoint
                for _edge, endpoint in connected
                if endpoint.role is InputAssetRole.MASK
            )
            if len(images) != 1 or not masks:
                continue
            surface = surfaces.get(images[0].node_name)
            if surface is None:
                continue
            candidates.extend(
                InputCanvasMaskBinding(
                    surface=surface,
                    mask_endpoint=mask_endpoint,
                    consumer_node_name=consumer_name,
                )
                for mask_endpoint in masks
            )
        return tuple(candidates)


def _unique_authored_bindings(
    candidates: tuple[InputCanvasMaskBinding, ...],
) -> tuple[
    tuple[InputCanvasMaskBinding, ...],
    dict[str, tuple[InputCanvasMaskBinding, ...]],
]:
    """Keep masks that resolve to exactly one authored surface."""

    grouped: dict[str, list[InputCanvasMaskBinding]] = {}
    for binding in candidates:
        grouped.setdefault(binding.mask_endpoint.node_name, []).append(binding)
    bindings: list[InputCanvasMaskBinding] = []
    ambiguous: dict[str, tuple[InputCanvasMaskBinding, ...]] = {}
    for mask_node_name, mask_candidates in grouped.items():
        distinct_surfaces = {
            candidate.surface.identity for candidate in mask_candidates
        }
        if len(distinct_surfaces) != 1:
            ambiguous[mask_node_name] = tuple(mask_candidates)
            continue
        bindings.append(mask_candidates[0])
    return tuple(bindings), ambiguous


def _consumer_accepts_endpoint(
    edge: WorkflowGraphEdge,
    endpoint: InputAssetEndpoint,
    topology: WorkflowGraphTopology,
    definitions: Mapping[str, Mapping[str, object]],
) -> bool:
    """Reject consumer sockets whose live type contradicts the endpoint role."""

    consumer = topology.nodes.get(edge.consumer_name, {})
    definition = definitions.get(node_class_type(consumer), {})
    input_type = declared_input_type(definition, edge.consumer_field_key)
    return input_type is None or input_type == endpoint.role.value.upper()


def _mask_consumer_identity(
    topology: WorkflowGraphTopology,
    mask_endpoint: InputAssetEndpoint,
    convergence_node_names: tuple[str, ...],
) -> str:
    """Return a deterministic diagnostic consumer identity for a synthetic binding."""

    consumers = tuple(
        dict.fromkeys(
            edge.consumer_name
            for edge in topology.outgoing_edges(
                mask_endpoint.node_name,
                mask_endpoint.output_index,
            )
        )
    )
    if len(consumers) == 1:
        return consumers[0]
    return convergence_node_names[0] if convergence_node_names else ""


__all__ = ["InputCanvasPlanService"]
