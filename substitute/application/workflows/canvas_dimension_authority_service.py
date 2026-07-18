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

"""Resolve mask-only canvas dimensions from spatial-root graph provenance."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import TypeGuard

from substitute.application.workflows.workflow_graph_topology import (
    WorkflowGraphTopology,
)
from substitute.domain.node_behavior.dimension_fields import (
    DimensionFieldPair,
    infer_dimension_field_pairs,
)
from substitute.domain.workflow import InputAssetEndpoint
from substitute.domain.workflow.input_canvas_plan import (
    CanvasDimensionAuthority,
    CanvasDimensionResolution,
    CanvasDimensions,
)


@dataclass(frozen=True, slots=True)
class _DimensionCandidate:
    """Capture one relevant spatial root and its concrete dimension evidence."""

    node_name: str
    output_index: int
    output_type: str
    pair: DimensionFieldPair
    dimensions: CanvasDimensions
    convergence_node_names: tuple[str, ...]
    convergence_distance: int


class CanvasDimensionAuthorityService:
    """Select conservative spatial-root dimension authorities for mask endpoints."""

    def resolve(
        self,
        mask_endpoint: InputAssetEndpoint,
        topology: WorkflowGraphTopology,
    ) -> CanvasDimensionResolution:
        """Resolve one safe size whose spatial lineage converges with the mask."""

        mask_distances = topology.downstream_distances_from_socket(
            mask_endpoint.node_name,
            mask_endpoint.output_index,
        )
        if not mask_distances:
            return CanvasDimensionResolution.missing("mask_output_is_unused")

        candidates = tuple(
            candidate
            for socket in topology.canvas_source_sockets()
            if (
                candidate := self._candidate_for_socket(
                    socket=socket,
                    topology=topology,
                    mask_distances=mask_distances,
                )
            )
            is not None
        )
        if not candidates:
            return CanvasDimensionResolution.missing(
                "no_relevant_spatial_root_with_dimensions"
            )

        preferred = _prefer_latent_candidates(candidates)
        dimensions = {candidate.dimensions for candidate in preferred}
        if len(dimensions) != 1:
            return CanvasDimensionResolution.ambiguous(
                "relevant_spatial_roots_disagree",
                tuple(candidate.node_name for candidate in preferred),
            )

        ordered = tuple(
            sorted(
                preferred,
                key=lambda candidate: (
                    candidate.convergence_distance,
                    candidate.node_name,
                    candidate.output_index,
                ),
            )
        )
        authority = CanvasDimensionAuthority(
            dimensions=ordered[0].dimensions,
            node_names=tuple(candidate.node_name for candidate in ordered),
            field_pairs=tuple(
                (candidate.pair.width_key, candidate.pair.height_key)
                for candidate in ordered
            ),
            convergence_node_names=tuple(
                dict.fromkeys(
                    node_name
                    for candidate in ordered
                    for node_name in candidate.convergence_node_names
                )
            ),
            fingerprint=_authority_fingerprint(ordered),
        )
        return CanvasDimensionResolution.resolved(authority)

    @staticmethod
    def _candidate_for_socket(
        *,
        socket: tuple[str, int, str],
        topology: WorkflowGraphTopology,
        mask_distances: dict[str, int],
    ) -> _DimensionCandidate | None:
        """Build a candidate only when one spatial root has unambiguous fields."""

        node_name, output_index, output_type = socket
        input_keys = topology.input_keys(node_name)
        pairs = infer_dimension_field_pairs(input_keys)
        if len(pairs) != 1:
            return None
        pair = pairs[0]
        width = topology.input_value(node_name, pair.width_key)
        height = topology.input_value(node_name, pair.height_key)
        if not _is_positive_int(width) or not _is_positive_int(height):
            return None

        source_distances = topology.downstream_distances_from_socket(
            node_name,
            output_index,
        )
        common_nodes = set(mask_distances).intersection(source_distances)
        if not common_nodes:
            return None
        minimum_distance = min(
            mask_distances[node_name] + source_distances[node_name]
            for node_name in common_nodes
        )
        convergence_nodes = tuple(
            sorted(
                node_name
                for node_name in common_nodes
                if mask_distances[node_name] + source_distances[node_name]
                == minimum_distance
            )
        )
        return _DimensionCandidate(
            node_name=node_name,
            output_index=output_index,
            output_type=output_type,
            pair=pair,
            dimensions=CanvasDimensions(width=width, height=height),
            convergence_node_names=convergence_nodes,
            convergence_distance=minimum_distance,
        )


def _prefer_latent_candidates(
    candidates: tuple[_DimensionCandidate, ...],
) -> tuple[_DimensionCandidate, ...]:
    """Prefer latent roots over procedural image roots in mixed generation regions."""

    latent = tuple(
        candidate for candidate in candidates if candidate.output_type == "LATENT"
    )
    return latent or candidates


def _is_positive_int(value: object) -> TypeGuard[int]:
    """Return whether a value is a concrete positive integer rather than a link."""

    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _authority_fingerprint(candidates: tuple[_DimensionCandidate, ...]) -> str:
    """Return a stable invalidation identity for resolved graph evidence."""

    payload = [
        {
            "node": candidate.node_name,
            "output": candidate.output_index,
            "type": candidate.output_type,
            "width_key": candidate.pair.width_key,
            "height_key": candidate.pair.height_key,
            "width": candidate.dimensions.width,
            "height": candidate.dimensions.height,
            "convergence": candidate.convergence_node_names,
        }
        for candidate in candidates
    ]
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["CanvasDimensionAuthorityService"]
