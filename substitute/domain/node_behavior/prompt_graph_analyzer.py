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

"""Infer prompt roles from authored names and typed conditioning flow."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from .models import PromptRole
from .prompt_candidate_policy import (
    PromptCandidatePolicy,
    PromptCandidateSelection,
    is_text_encoder_type,
    normalized_type,
    role_from_name,
    role_from_semantic_sink,
)
from .prompt_graph import (
    PromptAmbiguityReason,
    PromptDetectionResult,
    PromptEvidence,
    PromptEvidenceKind,
    PromptFieldLocator,
    PromptGraphField,
    PromptGraphNode,
    PromptGraphSource,
    PromptRoleAmbiguity,
    PromptRoleDetection,
    PromptSemanticGraph,
    PromptSinkLocator,
)

_CONDITIONING = "CONDITIONING"
_STRING = "STRING"


class PromptGraphAnalyzer:
    """Resolve prompt roles without relying on encoder class names."""

    def __init__(self) -> None:
        """Initialize deterministic candidate resolution policy."""

        self._candidate_policy = PromptCandidatePolicy()

    def analyze(self, graph: PromptSemanticGraph) -> PromptDetectionResult:
        """Return deterministic prompt roles for one isolated graph section."""

        fields = {
            field.locator: field
            for node in graph.nodes.values()
            for field in node.fields
        }
        evidence_by_role: dict[
            PromptFieldLocator,
            dict[PromptRole, list[PromptEvidence]],
        ] = defaultdict(lambda: defaultdict(list))
        sinks_by_role: dict[
            PromptFieldLocator,
            dict[PromptRole, list[PromptSinkLocator]],
        ] = defaultdict(lambda: defaultdict(list))
        ambiguities: list[PromptRoleAmbiguity] = []

        self._collect_authored_role_evidence(
            graph=graph,
            evidence_by_role=evidence_by_role,
            ambiguities=ambiguities,
        )
        self._collect_topology_evidence(
            graph=graph,
            evidence_by_role=evidence_by_role,
            sinks_by_role=sinks_by_role,
            ambiguities=ambiguities,
        )

        ambiguous_locators = {
            locator for ambiguity in ambiguities for locator in ambiguity.locators
        }
        detections: list[PromptRoleDetection] = []
        for locator, role_evidence in sorted(evidence_by_role.items()):
            if locator in ambiguous_locators:
                continue
            if len(role_evidence) != 1:
                ambiguities.append(
                    PromptRoleAmbiguity(
                        locators=(locator,),
                        reason=PromptAmbiguityReason.CONFLICTING_ROLES,
                        detail="Editable field has both positive and negative evidence.",
                    )
                )
                ambiguous_locators.add(locator)
                continue
            role, collected = next(iter(role_evidence.items()))
            field = fields.get(locator)
            if field is None:
                continue
            supporting = list(collected)
            supporting.extend(self._candidate_policy.candidate_evidence(field))
            detections.append(
                PromptRoleDetection(
                    locator=locator,
                    role=role,
                    evidence=_deduplicated_evidence(supporting),
                    semantic_sinks=tuple(
                        dict.fromkeys(sinks_by_role[locator].get(role, ()))
                    ),
                )
            )

        detections, mixed_ambiguities = self._withhold_mixed_node_roles(detections)
        ambiguities.extend(mixed_ambiguities)
        return PromptDetectionResult(
            detections=tuple(detections),
            ambiguities=_deduplicated_ambiguities(ambiguities),
        )

    def _collect_authored_role_evidence(
        self,
        *,
        graph: PromptSemanticGraph,
        evidence_by_role: dict[
            PromptFieldLocator,
            dict[PromptRole, list[PromptEvidence]],
        ],
        ambiguities: list[PromptRoleAmbiguity],
    ) -> None:
        """Collect high-confidence authored role evidence from candidate fields."""

        for node in graph.nodes.values():
            node_role = role_from_name(node.title)
            role_fields = [
                field
                for field in node.fields
                if self._candidate_policy.is_authored_candidate(field)
            ]
            if node_role is not None:
                selection = self._candidate_policy.select(role_fields, node_role)
                if selection.ambiguity is not None:
                    ambiguities.append(selection.ambiguity)
                for field in selection.fields:
                    evidence_by_role[field.locator][node_role].append(
                        PromptEvidence(
                            PromptEvidenceKind.AUTHORED_NODE_ROLE,
                            node.title,
                        )
                    )
            for field in role_fields:
                field_role = role_from_name(field.label)
                if field_role is not None:
                    evidence_by_role[field.locator][field_role].append(
                        PromptEvidence(
                            PromptEvidenceKind.AUTHORED_FIELD_ROLE,
                            field.label,
                        )
                    )

    def _collect_topology_evidence(
        self,
        *,
        graph: PromptSemanticGraph,
        evidence_by_role: dict[
            PromptFieldLocator,
            dict[PromptRole, list[PromptEvidence]],
        ],
        sinks_by_role: dict[
            PromptFieldLocator,
            dict[PromptRole, list[PromptSinkLocator]],
        ],
        ambiguities: list[PromptRoleAmbiguity],
    ) -> None:
        """Trace semantic conditioning sink roles back to editable strings."""

        for node in graph.nodes.values():
            model_lineage_sources = frozenset(
                node_input.source.node_name
                for node_input in node.inputs
                if normalized_type(node_input.type_name) == "MODEL"
                and node_input.source is not None
            )
            for node_input in node.inputs:
                role = role_from_semantic_sink(node_input.name, node_input.type_name)
                if role is None or node_input.source is None:
                    continue
                selections = self._trace_conditioning_source(
                    graph=graph,
                    source=node_input.source,
                    role=role,
                    visited=frozenset(),
                    model_lineage_sources=model_lineage_sources,
                )
                for selection in selections:
                    if selection.ambiguity is not None:
                        ambiguities.append(selection.ambiguity)
                    for field in selection.fields:
                        sinks_by_role[field.locator][role].append(
                            PromptSinkLocator(node.name, node_input.name)
                        )
                        evidence_by_role[field.locator][role].extend(
                            (
                                PromptEvidence(
                                    PromptEvidenceKind.SEMANTIC_SINK,
                                    f"{node.name}.{node_input.name}",
                                ),
                                PromptEvidence(
                                    PromptEvidenceKind.CONDITIONING_FLOW,
                                    f"{field.locator.node_name}->{node.name}",
                                ),
                                *selection.evidence,
                            )
                        )

    def _trace_conditioning_source(
        self,
        *,
        graph: PromptSemanticGraph,
        source: PromptGraphSource,
        role: PromptRole,
        visited: frozenset[PromptGraphSource],
        model_lineage_sources: frozenset[str],
    ) -> tuple[PromptCandidateSelection, ...]:
        """Trace one conditioning edge through transforms to encoding boundaries."""

        if source in visited:
            return ()
        node = graph.nodes.get(source.node_name)
        if node is None:
            return ()
        output = node.output(source.output_slot)
        if output is None or normalized_type(output.type_name) != _CONDITIONING:
            return ()
        conditioning_sources = tuple(
            node_input.source
            for node_input in node.inputs
            if normalized_type(node_input.type_name) == _CONDITIONING
            and node_input.source is not None
        )
        if conditioning_sources:
            next_visited = visited | {source}
            return tuple(
                selection
                for conditioning_source in conditioning_sources
                for selection in self._trace_conditioning_source(
                    graph=graph,
                    source=conditioning_source,
                    role=role,
                    visited=next_visited,
                    model_lineage_sources=model_lineage_sources,
                )
            )
        candidates = self._encoding_boundary_candidates(graph=graph, node=node)
        if not candidates:
            return ()
        selection = self._candidate_policy.select(candidates, role)
        interface_inputs = tuple(
            node_input
            for node_input in node.inputs
            if is_text_encoder_type(node_input.type_name)
        )
        interface_evidence: list[PromptEvidence] = []
        if interface_inputs:
            interface_evidence.append(
                PromptEvidence(
                    PromptEvidenceKind.TEXT_ENCODER_INTERFACE,
                    ",".join(sorted({item.type_name for item in interface_inputs})),
                )
            )
        text_model_sources = {
            item.source.node_name
            for item in interface_inputs
            if item.source is not None
        }
        shared_sources = text_model_sources & model_lineage_sources
        if shared_sources:
            interface_evidence.append(
                PromptEvidence(
                    PromptEvidenceKind.SHARED_MODEL_LINEAGE,
                    ",".join(sorted(shared_sources)),
                )
            )
        return (
            replace(
                selection,
                evidence=tuple(interface_evidence),
            ),
        )

    def _encoding_boundary_candidates(
        self,
        *,
        graph: PromptSemanticGraph,
        node: PromptGraphNode,
    ) -> tuple[PromptGraphField, ...]:
        """Return viable local or upstream strings feeding one encoder boundary."""

        candidates = list(node.fields)
        for node_input in node.inputs:
            if (
                normalized_type(node_input.type_name) != _STRING
                or node_input.source is None
            ):
                continue
            candidates.extend(
                self._trace_string_source(
                    graph=graph,
                    source=node_input.source,
                    visited=frozenset(),
                )
            )
        return tuple(dict.fromkeys(candidates))

    def _trace_string_source(
        self,
        *,
        graph: PromptSemanticGraph,
        source: PromptGraphSource,
        visited: frozenset[PromptGraphSource],
    ) -> tuple[PromptGraphField, ...]:
        """Trace a typed string edge back to its editable field owner."""

        if source in visited:
            return ()
        node = graph.nodes.get(source.node_name)
        if node is None:
            return ()
        output = node.output(source.output_slot)
        if output is None or normalized_type(output.type_name) != _STRING:
            return ()
        if node.fields:
            return node.fields
        next_visited = visited | {source}
        return tuple(
            field
            for node_input in node.inputs
            if normalized_type(node_input.type_name) == _STRING
            and node_input.source is not None
            for field in self._trace_string_source(
                graph=graph,
                source=node_input.source,
                visited=next_visited,
            )
        )

    @staticmethod
    def _withhold_mixed_node_roles(
        detections: list[PromptRoleDetection],
    ) -> tuple[list[PromptRoleDetection], list[PromptRoleAmbiguity]]:
        """Withhold cards whose single title cannot represent mixed prompt roles."""

        roles_by_node: dict[str, set[PromptRole]] = defaultdict(set)
        locators_by_node: dict[str, list[PromptFieldLocator]] = defaultdict(list)
        for detection in detections:
            roles_by_node[detection.locator.node_name].add(detection.role)
            locators_by_node[detection.locator.node_name].append(detection.locator)
        mixed_nodes = {
            node_name for node_name, roles in roles_by_node.items() if len(roles) > 1
        }
        retained = [
            detection
            for detection in detections
            if detection.locator.node_name not in mixed_nodes
        ]
        ambiguities = [
            PromptRoleAmbiguity(
                locators=tuple(sorted(locators_by_node[node_name])),
                reason=PromptAmbiguityReason.MIXED_NODE_ROLES,
                detail="One node card contains both positive and negative fields.",
            )
            for node_name in sorted(mixed_nodes)
        ]
        return retained, ambiguities


def _deduplicated_evidence(
    evidence: list[PromptEvidence],
) -> tuple[PromptEvidence, ...]:
    """Return stable evidence without repeated facts."""

    return tuple(dict.fromkeys(evidence))


def _deduplicated_ambiguities(
    ambiguities: list[PromptRoleAmbiguity],
) -> tuple[PromptRoleAmbiguity, ...]:
    """Return stable ambiguity records without repeated causes."""

    return tuple(dict.fromkeys(ambiguities))


__all__ = ["PromptGraphAnalyzer"]
