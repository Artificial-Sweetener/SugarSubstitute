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

"""Normalize explicitly proven legacy node aliases before workflow analysis."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy

from substitute.application.ports import NodeDefinitionGateway
from substitute.domain.common import JsonObject
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.direct_workflows.node_compatibility")
_LEGACY_CLASS = "SafeMaskToImage"
_CORE_CLASS = "MaskToImage"
_LEGACY_MODULE = "custom_nodes.comfyui_fearnworksnodes"
_CORE_MODULE = "comfy_extras.nodes_mask"


class DirectWorkflowNodeCompatibilityService:
    """Apply narrow node aliases only when saved and live contracts agree."""

    def __init__(self, node_definitions: NodeDefinitionGateway) -> None:
        """Store the live Comfy definition boundary used as compatibility proof."""

        self._node_definitions = node_definitions

    def normalize(self, workflow: Mapping[str, object]) -> JsonObject:
        """Return a detached workflow with every proven legacy reference replaced."""

        if not _contains_class_reference(workflow, _LEGACY_CLASS):
            return deepcopy(dict(workflow))
        saved_definitions = tuple(_saved_definitions(workflow, _LEGACY_CLASS))
        if not saved_definitions or any(
            not _is_mask_to_image_contract(definition, module=_LEGACY_MODULE)
            for definition in saved_definitions
        ):
            log_warning(
                _LOGGER,
                "Rejected legacy workflow node alias because its saved contract is unavailable or incompatible",
                legacy_class=_LEGACY_CLASS,
                replacement_class=_CORE_CLASS,
            )
            return deepcopy(dict(workflow))
        live_definition = _required_definition(
            self._node_definitions,
            _CORE_CLASS,
        )
        if not _is_mask_to_image_contract(live_definition, module=_CORE_MODULE):
            log_warning(
                _LOGGER,
                "Rejected legacy workflow node alias because the live replacement contract is incompatible",
                legacy_class=_LEGACY_CLASS,
                replacement_class=_CORE_CLASS,
            )
            return deepcopy(dict(workflow))
        normalized = deepcopy(dict(workflow))
        replacement_count = _rewrite_legacy_mask_nodes(
            normalized,
            replacement_definition=live_definition,
        )
        log_info(
            _LOGGER,
            "Normalized a proven legacy workflow node alias",
            legacy_class=_LEGACY_CLASS,
            replacement_class=_CORE_CLASS,
            replacement_count=replacement_count,
        )
        return normalized


def _required_definition(
    gateway: NodeDefinitionGateway,
    class_type: str,
) -> Mapping[str, object]:
    """Return one exact live definition or an empty mapping."""

    payload = gateway.get_node_definition(class_type)
    definition = payload.get(class_type)
    if not isinstance(definition, Mapping):
        payload = gateway.get_required_node_definition(class_type)
        definition = payload.get(class_type)
    return definition if isinstance(definition, Mapping) else {}


def _contains_class_reference(value: object, class_type: str) -> bool:
    """Return whether nested workflow data names one executable class."""

    if isinstance(value, Mapping):
        if value.get("type") == class_type or value.get("class_type") == class_type:
            return True
        return any(
            _contains_class_reference(child, class_type) for child in value.values()
        )
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return any(_contains_class_reference(child, class_type) for child in value)
    return False


def _saved_definitions(
    value: object,
    class_type: str,
) -> Iterable[Mapping[str, object]]:
    """Yield captured definitions that explicitly own one saved class name."""

    if isinstance(value, Mapping):
        candidate = value.get(class_type)
        if isinstance(candidate, Mapping) and candidate.get("name") == class_type:
            yield candidate
        for child in value.values():
            yield from _saved_definitions(child, class_type)
        return
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for child in value:
            yield from _saved_definitions(child, class_type)


def _is_mask_to_image_contract(
    definition: Mapping[str, object],
    *,
    module: str,
) -> bool:
    """Return whether a definition proves the exact one-mask-to-one-image contract."""

    if definition.get("python_module") != module:
        return False
    inputs = definition.get("input")
    if not isinstance(inputs, Mapping):
        return False
    required = inputs.get("required")
    if not isinstance(required, Mapping) or tuple(required) != ("mask",):
        return False
    if _input_type(required.get("mask")) != "MASK":
        return False
    for optional_group in ("optional", "hidden"):
        values = inputs.get(optional_group)
        if isinstance(values, Mapping) and values:
            return False
    return _text_sequence(definition.get("output")) == ("IMAGE",)


def _input_type(value: object) -> str | None:
    """Return the leading Comfy input type from one serialized field definition."""

    if not isinstance(value, Sequence) or isinstance(value, str | bytes) or not value:
        return None
    return value[0] if isinstance(value[0], str) else None


def _text_sequence(value: object) -> tuple[str, ...]:
    """Return a text tuple only for a fully textual JSON sequence."""

    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    if not all(isinstance(item, str) for item in value):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _rewrite_legacy_mask_nodes(
    value: object,
    *,
    replacement_definition: Mapping[str, object],
) -> int:
    """Rewrite proven legacy nodes and captured definitions in one detached graph."""

    replacements = 0
    if isinstance(value, dict):
        saved_definition = value.get(_LEGACY_CLASS)
        if (
            isinstance(saved_definition, Mapping)
            and saved_definition.get("name") == _LEGACY_CLASS
        ):
            del value[_LEGACY_CLASS]
            value[_CORE_CLASS] = deepcopy(dict(replacement_definition))
        owns_reference = False
        for key in ("type", "class_type"):
            if value.get(key) == _LEGACY_CLASS:
                value[key] = _CORE_CLASS
                owns_reference = True
                replacements += 1
        if owns_reference:
            properties = value.get("properties")
            if isinstance(properties, dict):
                properties["cnr_id"] = "comfy-core"
                properties.pop("aux_id", None)
                properties.pop("ver", None)
                if properties.get("Node name for S&R") == _LEGACY_CLASS:
                    properties["Node name for S&R"] = _CORE_CLASS
        for child in tuple(value.values()):
            replacements += _rewrite_legacy_mask_nodes(
                child,
                replacement_definition=replacement_definition,
            )
    elif isinstance(value, list):
        for child in value:
            replacements += _rewrite_legacy_mask_nodes(
                child,
                replacement_definition=replacement_definition,
            )
    return replacements


__all__ = ["DirectWorkflowNodeCompatibilityService"]
