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

"""Resolve effective scheduled LoRAs for a prompt editor context."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Hashable, Protocol

from substitute.application.model_metadata import RichChoiceContext, RichChoiceResolver
from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    ResolvedFieldSpec,
    extract_live_list_options,
)
from substitute.application.ports import NodeDefinitionGateway
from substitute.domain.common import JsonValue

from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
    PromptScheduledLoraService,
    scheduled_lora_from_catalog_item,
    scheduled_lora_from_model_catalog_item,
)
from substitute.application.prompt_editor.features.workflow_graph import (
    upstream_node_ids_from_nodes,
)


class ScheduledLoraProvider(Protocol):
    """Return scheduled LoRAs relevant to a prompt editor context."""

    def scheduled_loras_for_prompt_context(
        self,
        *,
        workflow_context: WorkflowPromptContext,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        prompt_text: str,
    ) -> tuple[PromptScheduledLora, ...]:
        """Return effective scheduled LoRAs for the supplied prompt field."""


@dataclass(frozen=True, slots=True)
class WorkflowPromptContext:
    """Carry workflow state required for effective prompt-context resolution."""

    cube_states: Mapping[str, object]
    stack_order: Sequence[str]
    workflow_overrides: Mapping[str, object]
    behavior_snapshot: EditorBehaviorSnapshot | None
    cache_token: tuple[Hashable, ...] = ()


class EffectiveScheduledLoraProvider:
    """Resolve inline, cube-field, and graph-effective scheduled LoRAs."""

    def __init__(
        self,
        *,
        prompt_scheduled_lora_service: PromptScheduledLoraService,
        prompt_lora_catalog_service: PromptLoraCatalogLookup,
        rich_choice_resolver: RichChoiceResolver,
        node_definition_gateway: NodeDefinitionGateway,
    ) -> None:
        """Store collaborators used for effective scheduled-LoRA resolution."""

        self._prompt_scheduled_lora_service = prompt_scheduled_lora_service
        self._prompt_lora_catalog_service = prompt_lora_catalog_service
        self._rich_choice_resolver = rich_choice_resolver
        self._node_definition_gateway = node_definition_gateway
        self._document_projector = PromptDocumentProjector()
        self._cube_field_cache: dict[
            tuple[tuple[Hashable, ...], str | None],
            tuple[PromptScheduledLora, ...],
        ] = {}
        self._graph_context_cache: dict[
            tuple[tuple[Hashable, ...], str | None, str, str],
            tuple[PromptScheduledLora, ...],
        ] = {}

    def scheduled_loras_for_prompt_context(
        self,
        *,
        workflow_context: WorkflowPromptContext,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        prompt_text: str,
    ) -> tuple[PromptScheduledLora, ...]:
        """Return effective scheduled LoRAs for the supplied prompt field."""

        inline_loras = self._prompt_scheduled_lora_service.inline_scheduled_loras(
            prompt_text=prompt_text,
            document_projector=self._document_projector,
            lora_catalog=self._prompt_lora_catalog_service,
        )
        cube_field_loras = self._cached_cube_field_scheduled_loras(
            workflow_context=workflow_context,
            cube_alias=cube_alias,
        )
        graph_loras = self._cached_graph_effective_scheduled_loras(
            workflow_context=workflow_context,
            cube_alias=cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
        )
        merged = self._prompt_scheduled_lora_service.merge_scheduled_loras(
            inline_loras,
            graph_loras,
            cube_field_loras,
        )
        return merged

    def _cached_cube_field_scheduled_loras(
        self,
        *,
        workflow_context: WorkflowPromptContext,
        cube_alias: str | None,
    ) -> tuple[PromptScheduledLora, ...]:
        """Return cube-field LoRAs from a workflow-context cache when possible."""

        if not workflow_context.cache_token:
            return self._cube_field_scheduled_loras(
                workflow_context=workflow_context,
                cube_alias=cube_alias,
            )
        cache_key = (workflow_context.cache_token, cube_alias)
        cached = self._cube_field_cache.get(cache_key)
        if cached is not None:
            return cached
        scheduled_loras = self._cube_field_scheduled_loras(
            workflow_context=workflow_context,
            cube_alias=cube_alias,
        )
        self._cube_field_cache[cache_key] = scheduled_loras
        return scheduled_loras

    def _cached_graph_effective_scheduled_loras(
        self,
        *,
        workflow_context: WorkflowPromptContext,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> tuple[PromptScheduledLora, ...]:
        """Return graph-effective LoRAs from a context cache when possible."""

        if not workflow_context.cache_token:
            return self._graph_effective_scheduled_loras(
                workflow_context=workflow_context,
                cube_alias=cube_alias,
                prompt_node_name=prompt_node_name,
                prompt_field_key=prompt_field_key,
            )
        cache_key = (
            workflow_context.cache_token,
            cube_alias,
            prompt_node_name,
            prompt_field_key,
        )
        cached = self._graph_context_cache.get(cache_key)
        if cached is not None:
            return cached
        scheduled_loras = self._graph_effective_scheduled_loras(
            workflow_context=workflow_context,
            cube_alias=cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
        )
        self._graph_context_cache[cache_key] = scheduled_loras
        return scheduled_loras

    def _cube_field_scheduled_loras(
        self,
        *,
        workflow_context: WorkflowPromptContext,
        cube_alias: str | None,
    ) -> tuple[PromptScheduledLora, ...]:
        """Return LoRAs selected by enriched LIST fields in the prompt cube."""

        if cube_alias is None or workflow_context.behavior_snapshot is None:
            return ()
        field_specs_by_node = (
            workflow_context.behavior_snapshot.field_specs_by_alias.get(
                cube_alias,
                {},
            )
        )
        scheduled_loras: list[PromptScheduledLora] = []
        field_spec_count = 0
        for node_name, field_specs in field_specs_by_node.items():
            for field_spec in field_specs.values():
                field_spec_count += 1
                scheduled_lora = self._scheduled_lora_from_field_spec(
                    node_name=node_name,
                    field_spec=field_spec,
                )
                if scheduled_lora is not None:
                    scheduled_loras.append(scheduled_lora)
        result = tuple(scheduled_loras)
        return result

    def _scheduled_lora_from_field_spec(
        self,
        *,
        node_name: str,
        field_spec: ResolvedFieldSpec,
    ) -> PromptScheduledLora | None:
        """Resolve one field spec into a scheduled LoRA when it is an enriched LoRA LIST."""

        if field_spec.field_type != "LIST":
            return None
        options = self._list_choice_options(field_spec)
        if not options:
            return None
        resolution = self._rich_choice_resolver.resolve(
            options,
            context=RichChoiceContext(
                node_class=field_spec.class_type,
                node_name=node_name,
                field_key=field_spec.field_key,
            ),
        )
        current_value = "" if field_spec.value is None else str(field_spec.value)
        for item in resolution.items:
            if item.value != current_value:
                continue
            if item.model_kind != "loras" or item.catalog_item is None:
                return None
            prompt_item = self._prompt_lora_catalog_service.find_lora(
                item.catalog_item.backend_value
            )
            if prompt_item is not None:
                return scheduled_lora_from_catalog_item(
                    prompt_item,
                    source="cube_field",
                )
            return scheduled_lora_from_model_catalog_item(
                item.catalog_item,
                source="cube_field",
            )
        return None

    def _list_choice_options(self, field_spec: ResolvedFieldSpec) -> tuple[str, ...]:
        """Return exact LIST options from live definitions or behavior field info."""

        live_definition = self._node_definition_gateway.get_node_definition(
            field_spec.class_type
        )
        node_definition = live_definition.get(field_spec.class_type, {})
        if isinstance(node_definition, dict):
            input_section = node_definition.get("input", {})
            if isinstance(input_section, dict):
                raw_info = input_section.get("required", {}).get(
                    field_spec.field_key
                ) or input_section.get("optional", {}).get(field_spec.field_key)
                if (
                    isinstance(raw_info, list)
                    and raw_info
                    and isinstance(raw_info[0], list)
                    and all(isinstance(option, str) for option in raw_info[0])
                ):
                    return tuple(raw_info[0])
        return tuple(extract_live_list_options(field_spec.field_info))

    def _graph_effective_scheduled_loras(
        self,
        *,
        workflow_context: WorkflowPromptContext,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> tuple[PromptScheduledLora, ...]:
        """Return LoRA scheduler nodes feeding the editable prompt graph path."""

        if cube_alias is None:
            return ()
        cube = workflow_context.cube_states.get(cube_alias)
        buffer = getattr(cube, "buffer", None)
        nodes = buffer.get("nodes") if isinstance(buffer, Mapping) else None
        if not isinstance(nodes, Mapping):
            return ()
        return self._analyze_cube_graph_for_prompt(
            workflow_nodes=nodes,
            prompt_node_name=prompt_node_name,
        )

    def _analyze_cube_graph_for_prompt(
        self,
        *,
        workflow_nodes: Mapping[str, JsonValue],
        prompt_node_name: str,
    ) -> tuple[PromptScheduledLora, ...]:
        """Walk one Cube prompt branch and collect effective LoRA nodes."""

        if prompt_node_name not in workflow_nodes:
            return ()
        visited: set[str] = set()
        scheduled_loras: list[PromptScheduledLora] = []
        for node_id in upstream_node_ids_from_nodes(
            workflow_nodes=workflow_nodes,
            start_node_id=prompt_node_name,
            visited=visited,
        ):
            node = workflow_nodes.get(node_id)
            if not isinstance(node, Mapping) or not _is_lora_node(node):
                continue
            scheduled_lora = self._scheduled_lora_from_graph_node(node)
            if scheduled_lora is not None:
                scheduled_loras.append(scheduled_lora)
        return tuple(scheduled_loras)

    def _scheduled_lora_from_graph_node(
        self,
        node: Mapping[str, JsonValue],
    ) -> PromptScheduledLora | None:
        """Resolve one editable LoRA scheduler node into catalog metadata."""

        inputs = node.get("inputs", {})
        if not isinstance(inputs, Mapping):
            return None
        for key, value in inputs.items():
            if "lora" not in str(key).casefold() or not isinstance(value, str):
                continue
            prompt_item = self._prompt_lora_catalog_service.find_lora(value)
            if prompt_item is None:
                continue
            return scheduled_lora_from_catalog_item(
                prompt_item,
                source="graph_effective",
            )
        for value in inputs.values():
            if not isinstance(value, str) or "<lora:" not in value.casefold():
                continue
            inline_loras = self._prompt_scheduled_lora_service.inline_scheduled_loras(
                prompt_text=value,
                document_projector=self._document_projector,
                lora_catalog=self._prompt_lora_catalog_service,
            )
            if inline_loras:
                return replace(inline_loras[0], source="graph_effective")
        return None


def _is_lora_node(node: Mapping[str, JsonValue]) -> bool:
    """Return whether a compiled node looks like a LoRA scheduler/loader."""

    class_type = node.get("class_type")
    return isinstance(class_type, str) and "lora" in class_type.casefold()


__all__ = [
    "EffectiveScheduledLoraProvider",
    "ScheduledLoraProvider",
    "WorkflowPromptContext",
]
