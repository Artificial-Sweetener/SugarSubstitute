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

"""Resolve editor node definitions from graph-local and live Comfy metadata."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from substitute.application.ports import NodeDefinitionGateway
from substitute.domain.cubes import SubgraphWrapperDefinitionIndex
from substitute.domain.comfy_workflow.editor_definitions import (
    workflow_local_editor_definition,
)
from substitute.domain.comfy_workflow.native_widget_schema import (
    normalize_native_widget_definition,
)

from .list_value_resolver import extract_live_list_options
from .live_definition_authority import (
    LiveNodeDefinitionError,
    LiveNodeFieldDefinition,
    MissingLiveNodeDefinition,
)

_WRAPPER_STRUCTURAL_METADATA_KEYS = frozenset(
    {
        "subgraph_wrapper",
        "subgraph_id",
        "interface_id",
        "interface_type",
        "localized_name",
        "label",
        "min",
        "max",
        "step",
        "placeholder",
        "multiline",
        "dynamicPrompts",
        "shape",
        "body_node_type",
        "body_input_name",
        "default_source",
        "has_authored_default",
    }
)
_LIVE_METADATA_FALLBACK_SOURCE = "live_metadata_fallback"
_DYNAMIC_COMBO_TYPE = "COMFY_DYNAMICCOMBO_V3"


class EditorNodeDefinitionResolver:
    """Merge workflow-local widget schemas with optional live Comfy enrichment."""

    def __init__(self, gateway: NodeDefinitionGateway) -> None:
        """Store the live definition gateway used for optional enrichment."""

        self._gateway = gateway

    def resolve(
        self,
        *,
        class_type: str,
        node_data: Mapping[str, object],
        wrapper_definitions: SubgraphWrapperDefinitionIndex | None = None,
        cube_alias: str = "",
        node_name: str = "",
    ) -> Mapping[str, object] | None:
        """Return the best editor definition available for one node instance."""

        if wrapper_definitions is not None:
            wrapper_definition = wrapper_definitions.definition_for_class_type(
                class_type
            )
            if wrapper_definition is not None:
                return self._merge_wrapper_body_live_metadata(
                    wrapper_definition,
                    wrapper_definitions=wrapper_definitions,
                    cube_alias=cube_alias,
                    node_name=node_name,
                )

        local_definition = workflow_local_editor_definition(node_data)
        live_payload = self._gateway.get_node_definition(class_type)
        live_definition = (
            live_payload.get(class_type) if isinstance(live_payload, Mapping) else None
        )
        if isinstance(live_definition, Mapping):
            inputs = node_data.get("inputs")
            selected_values = inputs if isinstance(inputs, Mapping) else {}
            live_definition = normalize_native_widget_definition(
                live_definition,
                selected_values,
            )
            if local_definition is None:
                return deepcopy(dict(live_definition))
            return _merge_definitions(
                _without_stale_dynamic_descendants(
                    local_definition,
                    live_definition,
                ),
                live_definition,
            )
        if local_definition is not None:
            return deepcopy(dict(local_definition))
        return None

    def _merge_wrapper_body_live_metadata(
        self,
        wrapper_definition: Mapping[str, object],
        *,
        wrapper_definitions: SubgraphWrapperDefinitionIndex,
        cube_alias: str,
        node_name: str,
    ) -> Mapping[str, object]:
        """Enrich one wrapper interface from the linked body node definitions."""

        enriched = deepcopy(dict(wrapper_definition))
        input_section = enriched.get("input")
        if not isinstance(input_section, dict):
            return enriched
        for section_name in ("required", "optional"):
            section = input_section.get(section_name)
            if not isinstance(section, dict):
                continue
            for field_spec in section.values():
                self._merge_wrapper_field_body_live_metadata(
                    field_spec,
                    wrapper_definitions=wrapper_definitions,
                    cube_alias=cube_alias,
                    node_name=node_name,
                )
        return enriched

    def _merge_wrapper_field_body_live_metadata(
        self,
        field_spec: object,
        *,
        wrapper_definitions: SubgraphWrapperDefinitionIndex,
        cube_alias: str,
        node_name: str,
    ) -> None:
        """Replace one wrapper field's runtime portion with body metadata."""

        if (
            not isinstance(field_spec, list)
            or len(field_spec) < 2
            or not isinstance(field_spec[1], dict)
        ):
            return
        metadata = field_spec[1]
        body_node_type = metadata.get("body_node_type")
        body_input_name = metadata.get("body_input_name")
        if not isinstance(body_node_type, str) or not isinstance(
            body_input_name,
            str,
        ):
            return
        live_payload = self._gateway.get_required_node_definition(body_node_type)
        body_definition = live_payload.get(body_node_type)
        if not isinstance(body_definition, Mapping):
            nested = wrapper_definitions.definition_for_class_type(body_node_type)
            if nested is not None:
                body_definition = self._merge_wrapper_body_live_metadata(
                    nested,
                    wrapper_definitions=wrapper_definitions,
                    cube_alias=cube_alias,
                    node_name=node_name,
                )
        if not isinstance(body_definition, Mapping):
            raise LiveNodeDefinitionError(
                operation="resolve wrapper body node metadata",
                missing_definitions=(
                    MissingLiveNodeDefinition(
                        class_type=body_node_type,
                        cube_aliases=(cube_alias,),
                        node_names=(node_name,),
                    ),
                ),
            )
        body_field_info = _raw_field_definition(body_definition, body_input_name)
        if body_field_info is None:
            raise LiveNodeDefinitionError(
                operation="resolve wrapper body node metadata",
                missing_definitions=(),
                missing_fields=(
                    LiveNodeFieldDefinition(
                        class_type=body_node_type,
                        field_key=body_input_name,
                        field_type=None,
                        meta_info={},
                        field_info=None,
                    ),
                ),
            )
        body_metadata = _field_metadata(body_field_info)
        body_options = extract_live_list_options(body_field_info)
        if body_options:
            body_metadata["options"] = list(body_options)
        replacement_field = deepcopy(body_field_info)
        if not replacement_field:
            return
        if len(replacement_field) < 2 or not isinstance(
            replacement_field[1],
            Mapping,
        ):
            replacement_field = [replacement_field[0], {}, *replacement_field[1:]]
        replacement_metadata = deepcopy(body_metadata)
        if metadata.get("has_authored_default") is True and "default" in metadata:
            replacement_metadata["default"] = deepcopy(metadata["default"])
            replacement_metadata["default_source"] = metadata.get("default_source")
            replacement_metadata["has_authored_default"] = True
        elif "default" not in replacement_metadata and "default" in metadata:
            replacement_metadata["default"] = deepcopy(metadata["default"])
            replacement_metadata["default_source"] = metadata.get("default_source")
            replacement_metadata["has_authored_default"] = bool(
                metadata.get("has_authored_default")
            )
        else:
            replacement_metadata.setdefault(
                "default_source",
                _LIVE_METADATA_FALLBACK_SOURCE,
            )
            replacement_metadata.setdefault("has_authored_default", False)
        replacement_metadata.update(_wrapper_structural_metadata(metadata))
        replacement_field[1] = replacement_metadata
        field_spec[:] = replacement_field


def _merge_definitions(
    local_definition: Mapping[str, object],
    live_definition: Mapping[str, object],
) -> dict[str, object]:
    """Overlay authoritative live metadata while retaining local-only fields."""

    merged = deepcopy(dict(local_definition))
    for key, live_value in live_definition.items():
        if key != "input" or not isinstance(live_value, Mapping):
            merged[str(key)] = deepcopy(live_value)
            continue
        local_input = merged.get("input")
        merged_input = (
            deepcopy(dict(local_input)) if isinstance(local_input, Mapping) else {}
        )
        for section_name, live_section in live_value.items():
            if not isinstance(live_section, Mapping):
                merged_input[str(section_name)] = deepcopy(live_section)
                continue
            local_section = merged_input.get(section_name)
            merged_section = (
                deepcopy(dict(local_section))
                if isinstance(local_section, Mapping)
                else {}
            )
            merged_section.update(deepcopy(dict(live_section)))
            merged_input[str(section_name)] = merged_section
        merged["input"] = merged_input
    return merged


def _without_stale_dynamic_descendants(
    local_definition: Mapping[str, object],
    live_definition: Mapping[str, object],
) -> dict[str, object]:
    """Remove imported descendants superseded by an active live dynamic schema."""

    dynamic_prefixes = _dynamic_field_prefixes(live_definition)
    cleaned = deepcopy(dict(local_definition))
    if not dynamic_prefixes:
        return cleaned
    input_section = cleaned.get("input")
    if not isinstance(input_section, dict):
        return cleaned
    for section_name in ("required", "optional"):
        section = input_section.get(section_name)
        if not isinstance(section, dict):
            continue
        input_section[section_name] = {
            field_name: field_definition
            for field_name, field_definition in section.items()
            if not any(
                str(field_name).startswith(f"{prefix}.") for prefix in dynamic_prefixes
            )
        }
    return cleaned


def _dynamic_field_prefixes(definition: Mapping[str, object]) -> frozenset[str]:
    """Return normalized selectors whose descendants are live-schema-owned."""

    input_section = definition.get("input")
    if not isinstance(input_section, Mapping):
        return frozenset()
    prefixes: set[str] = set()
    for section_name in ("required", "optional"):
        section = input_section.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for field_name, field_definition in section.items():
            if not isinstance(field_name, str):
                continue
            metadata = _field_metadata(field_definition)
            if metadata.get("native_widget_type") == _DYNAMIC_COMBO_TYPE:
                prefixes.add(field_name)
    return frozenset(prefixes)


def _raw_field_definition(
    definition: Mapping[str, object],
    field_key: str,
) -> list[object] | None:
    """Return a detached required or optional field definition."""

    input_section = definition.get("input")
    if not isinstance(input_section, Mapping):
        return None
    for section_name in ("required", "optional"):
        section = input_section.get(section_name)
        if not isinstance(section, Mapping):
            continue
        field_info = section.get(field_key)
        if isinstance(field_info, list):
            return deepcopy(field_info)
    return None


def _field_metadata(field_info: list[object]) -> dict[str, object]:
    """Return copied metadata from one field definition."""

    if len(field_info) < 2 or not isinstance(field_info[1], Mapping):
        return {}
    return deepcopy(dict(field_info[1]))


def _wrapper_structural_metadata(
    metadata: Mapping[str, object],
) -> dict[str, object]:
    """Return wrapper-owned structural metadata retained during enrichment."""

    return {
        key: deepcopy(value)
        for key, value in metadata.items()
        if key in _WRAPPER_STRUCTURAL_METADATA_KEYS
    }


__all__ = ["EditorNodeDefinitionResolver"]
