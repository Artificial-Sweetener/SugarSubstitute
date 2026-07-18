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

"""Adapt graph-semantic prompt detections into existing node behavior patches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from substitute.domain.node_behavior.defaults import is_prompt_node_name
from substitute.domain.node_behavior.models import NodeBehaviorPatch, PromptRole
from substitute.domain.node_behavior.prompt_context_resolver import (
    PromptGraphContextResolver,
)
from substitute.domain.node_behavior.prompt_behavior_patch import (
    prompt_node_behavior_patch,
)
from substitute.domain.node_behavior.prompt_graph import (
    PromptDetectionResult,
    PromptGraphContext,
    PromptSemanticGraph,
)
from substitute.domain.node_behavior.prompt_graph_analyzer import PromptGraphAnalyzer
from substitute.domain.node_behavior.resolver import merge_node_behavior_patches

from .prompt_graph_factory import PromptSemanticGraphFactory
from .section_node_source import SectionNodeSource


@dataclass(frozen=True, slots=True)
class PromptBehaviorInference:
    """Carry graph diagnostics and per-node behavior patches for one section."""

    patches_by_node: Mapping[str, NodeBehaviorPatch]
    detection_result: PromptDetectionResult
    graph_contexts: tuple[PromptGraphContext, ...]


class PromptBehaviorInferenceService:
    """Own graph prompt analysis at the application behavior boundary."""

    def __init__(self) -> None:
        """Initialize pure graph construction and analysis collaborators."""

        self._graph_factory = PromptSemanticGraphFactory()
        self._analyzer = PromptGraphAnalyzer()
        self._context_resolver = PromptGraphContextResolver()

    def infer(
        self,
        sources: tuple[SectionNodeSource, ...],
    ) -> PromptBehaviorInference:
        """Return prompt patches without overriding literal prompt node rules."""

        graph = self._graph_factory.build(sources)
        result = self._analyzer.analyze(graph)
        patches = self._literal_prompt_patches(graph)
        for detection in result.detections:
            node_name = detection.locator.node_name
            if is_prompt_node_name(node_name):
                continue
            patches[node_name] = merge_node_behavior_patches(
                patches.get(node_name, NodeBehaviorPatch()),
                prompt_node_behavior_patch(
                    field_key=detection.locator.field_key,
                    role=detection.role,
                ),
            )
        return PromptBehaviorInference(
            patches_by_node=patches,
            detection_result=result,
            graph_contexts=self._context_resolver.resolve(result),
        )

    @staticmethod
    def _literal_prompt_patches(
        graph: PromptSemanticGraph,
    ) -> dict[str, NodeBehaviorPatch]:
        """Bind literal prompt aliases to their actual editable string field."""

        nodes = graph.nodes
        patches: dict[str, NodeBehaviorPatch] = {}
        for node_name, role in (
            ("positive_prompt", PromptRole.POSITIVE),
            ("negative_prompt", PromptRole.NEGATIVE),
        ):
            node = nodes.get(node_name)
            if node is None:
                continue
            fields = node.fields
            preferred = next(
                (
                    field
                    for field in fields
                    if field.locator.field_key == "prompt_template"
                ),
                None,
            )
            field = preferred or (fields[0] if len(fields) == 1 else None)
            if field is None:
                continue
            patches[node_name] = prompt_node_behavior_patch(
                field_key=field.locator.field_key,
                role=role,
            )
        return patches


__all__ = ["PromptBehaviorInference", "PromptBehaviorInferenceService"]
