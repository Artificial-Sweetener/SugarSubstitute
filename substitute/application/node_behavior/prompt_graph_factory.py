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

"""Project editor graph buffers into the prompt-semantic domain contract."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Mapping

from substitute.domain.node_behavior.prompt_graph import (
    PromptFieldLocator,
    PromptGraphField,
    PromptGraphInput,
    PromptGraphNode,
    PromptGraphOutput,
    PromptGraphSource,
    PromptSemanticGraph,
)

from .section_node_source import SectionNodeSource


class PromptSemanticGraphFactory:
    """Build one isolated semantic graph from prepared editor nodes."""

    def build(
        self,
        sources: tuple[SectionNodeSource, ...],
    ) -> PromptSemanticGraph:
        """Return a typed graph without retaining mutable editor buffers."""

        nodes = {source.node_name: self._build_node(source) for source in sources}
        return PromptSemanticGraph(nodes=nodes)

    def _build_node(self, source: SectionNodeSource) -> PromptGraphNode:
        """Return prompt-facing metadata for one prepared node."""

        definitions = _input_definitions(source.node_definition)
        workflow_inputs = _workflow_input_types(source.node_data)
        raw_inputs = source.node_data.get("inputs")
        values = raw_inputs if isinstance(raw_inputs, Mapping) else {}
        fields: list[PromptGraphField] = []
        inputs: list[PromptGraphInput] = []
        for field_key in source.input_keys:
            field_definition = definitions.get(field_key)
            type_name = _field_type(field_definition) or workflow_inputs.get(
                field_key, ""
            )
            value = values.get(field_key)
            link_source = _link_source(value)
            field = None
            if type_name.upper() == "STRING" and link_source is None:
                field = PromptGraphField(
                    locator=PromptFieldLocator(source.node_name, field_key),
                    node_title=source.node_title or source.node_name,
                    label=_field_label(field_key, field_definition),
                    multiline=_field_is_multiline(field_definition),
                )
                fields.append(field)
            inputs.append(
                PromptGraphInput(
                    name=field_key,
                    type_name=type_name,
                    source=link_source,
                    field=field,
                )
            )
        return PromptGraphNode(
            name=source.node_name,
            title=source.node_title or source.node_name,
            inputs=tuple(inputs),
            outputs=_node_outputs(source.node_data, source.node_definition),
            fields=tuple(fields),
        )


def _input_definitions(
    node_definition: Mapping[str, object] | None,
) -> dict[str, object]:
    """Return required and optional input definitions by field name."""

    if not isinstance(node_definition, Mapping):
        return {}
    raw_input = node_definition.get("input")
    if not isinstance(raw_input, Mapping):
        return {}
    definitions: dict[str, object] = {}
    for section_name in ("required", "optional"):
        section = raw_input.get(section_name)
        if isinstance(section, Mapping):
            definitions.update((str(key), value) for key, value in section.items())
    return definitions


def _field_type(field_definition: object) -> str | None:
    """Return the scalar Comfy type declared for one field."""

    if not isinstance(field_definition, Sequence) or isinstance(
        field_definition, str | bytes
    ):
        return None
    if not field_definition or not isinstance(field_definition[0], str):
        return None
    return field_definition[0].strip()


def _field_metadata(field_definition: object) -> Mapping[str, object]:
    """Return metadata declared beside one Comfy field type."""

    if not isinstance(field_definition, Sequence) or isinstance(
        field_definition, str | bytes
    ):
        return {}
    if len(field_definition) < 2 or not isinstance(field_definition[1], Mapping):
        return {}
    return field_definition[1]


def _field_label(field_key: str, field_definition: object) -> str:
    """Return an authored field label with its stable key as fallback."""

    label = _field_metadata(field_definition).get("label")
    return label.strip() if isinstance(label, str) and label.strip() else field_key


def _field_is_multiline(field_definition: object) -> bool:
    """Return whether Comfy declares a multiline string widget."""

    return _field_metadata(field_definition).get("multiline") is True


def _link_source(value: object) -> PromptGraphSource | None:
    """Return a typed link endpoint from an API-shaped input value."""

    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return None
    if len(value) != 2 or not isinstance(value[1], int):
        return None
    node_name = value[0]
    if not isinstance(node_name, str | int):
        return None
    return PromptGraphSource(str(node_name), value[1])


def _workflow_input_types(node_data: Mapping[str, object]) -> dict[str, str]:
    """Return preserved Comfy input types when live definitions omit them."""

    workflow = node_data.get("_workflow")
    if not isinstance(workflow, Mapping):
        return {}
    raw_inputs = workflow.get("inputs")
    if not isinstance(raw_inputs, Sequence) or isinstance(raw_inputs, str | bytes):
        return {}
    result: dict[str, str] = {}
    for raw_input in raw_inputs:
        if not isinstance(raw_input, Mapping):
            continue
        name = raw_input.get("name")
        type_name = raw_input.get("type")
        if isinstance(name, str) and isinstance(type_name, str):
            result[name] = type_name
    return result


def _node_outputs(
    node_data: Mapping[str, object],
    node_definition: Mapping[str, object] | None,
) -> tuple[PromptGraphOutput, ...]:
    """Return outputs from preserved workflow metadata or live definitions."""

    workflow = node_data.get("_workflow")
    if isinstance(workflow, Mapping):
        outputs = _outputs_from_workflow(workflow.get("outputs"))
        if outputs:
            return outputs
    if not isinstance(node_definition, Mapping):
        return ()
    raw_types = node_definition.get("output")
    if not isinstance(raw_types, Sequence) or isinstance(raw_types, str | bytes):
        return ()
    raw_names = node_definition.get("output_name")
    names = (
        tuple(raw_names)
        if isinstance(raw_names, Sequence) and not isinstance(raw_names, str | bytes)
        else ()
    )
    return tuple(
        PromptGraphOutput(
            slot=slot,
            name=str(names[slot]) if slot < len(names) else str(type_name),
            type_name=str(type_name),
        )
        for slot, type_name in enumerate(raw_types)
    )


def _outputs_from_workflow(payload: object) -> tuple[PromptGraphOutput, ...]:
    """Return output metadata preserved by direct workflow conversion."""

    if not isinstance(payload, Sequence) or isinstance(payload, str | bytes):
        return ()
    outputs: list[PromptGraphOutput] = []
    for fallback_slot, item in enumerate(payload):
        if not isinstance(item, Mapping):
            continue
        slot = item.get("slot", fallback_slot)
        if not isinstance(slot, int):
            continue
        outputs.append(
            PromptGraphOutput(
                slot=slot,
                name=str(item.get("name", slot)),
                type_name=str(item.get("type", "")),
            )
        )
    return tuple(outputs)


__all__ = ["PromptSemanticGraphFactory"]
