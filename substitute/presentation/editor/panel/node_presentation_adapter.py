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

"""Adapt editor node-card inputs to locale-neutral presentation requests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sugarsubstitute_shared.localization import ApplicationMessage

from substitute.application.localization import NodePresentationService
from substitute.application.node_behavior import ResolvedFieldSpec, ResolvedNodeBehavior
from substitute.application.ports import NodeDefinitionGateway
from substitute.domain.localization import (
    NodeFieldPresentationRequest,
    NodePresentation,
    NodePresentationRequest,
)
from substitute.domain.node_behavior import FieldLabelSource


def present_node_card(
    *,
    service: NodePresentationService,
    node_definition_gateway: NodeDefinitionGateway,
    node_name: str,
    node_type: str,
    field_specs: Mapping[str, ResolvedFieldSpec],
    resolved_behavior: ResolvedNodeBehavior,
) -> NodePresentation:
    """Project one card through the authoritative node-text service."""

    return service.present(
        build_node_presentation_request(
            node_definition_gateway=node_definition_gateway,
            node_name=node_name,
            node_type=node_type,
            field_specs=field_specs,
            resolved_behavior=resolved_behavior,
        )
    )


def build_node_presentation_request(
    *,
    node_definition_gateway: NodeDefinitionGateway,
    node_name: str,
    node_type: str,
    field_specs: Mapping[str, ResolvedFieldSpec],
    resolved_behavior: ResolvedNodeBehavior,
) -> NodePresentationRequest:
    """Capture stable authored and raw card text for repeated locale projection."""

    live_definition = _live_definition(node_definition_gateway, node_type)
    return NodePresentationRequest(
        class_type=node_type,
        node_name=node_name,
        authored_title=resolved_behavior.display_name,
        raw_display_name=_mapping_text(live_definition, "display_name"),
        raw_description=(
            _mapping_text(live_definition, "description")
            or _clean_text(resolved_behavior.card.tooltip)
        ),
        fields=tuple(_field_request(field_spec) for field_spec in field_specs.values()),
        outputs=_output_requests(live_definition),
    )


def _live_definition(
    gateway: NodeDefinitionGateway,
    node_type: str,
) -> Mapping[str, object]:
    """Return cached live metadata without initiating synchronous network work."""

    payload = gateway.get_node_definition(node_type)
    definition = payload.get(node_type) if isinstance(payload, Mapping) else None
    return definition if isinstance(definition, Mapping) else {}


def _field_request(field_spec: ResolvedFieldSpec) -> NodeFieldPresentationRequest:
    """Map typed label ownership to stable presentation candidates."""

    metadata = field_spec.meta_info
    label_source = field_spec.label_source
    label_override = field_spec.field_behavior.label_override
    authored_label: str | None = None
    application_label: ApplicationMessage | None = None
    raw_name: str | None = None
    if label_source is FieldLabelSource.APPLICATION:
        if not isinstance(label_override, ApplicationMessage):
            raise TypeError("Application-owned field labels must use app_text().")
        application_label = label_override
    elif label_source is FieldLabelSource.AUTHORED:
        if not isinstance(label_override, str):
            raise TypeError("Authored field labels must be plain text.")
        authored_label = _clean_text(label_override)
    elif label_source is FieldLabelSource.WRAPPER_AUTHORED:
        authored_label = _mapping_text(metadata, "label")
    else:
        raw_name = (
            _mapping_text(metadata, "localized_name")
            or _mapping_text(metadata, "display_name")
            or _mapping_text(metadata, "label")
        )
    return NodeFieldPresentationRequest(
        field_key=field_spec.field_key,
        authored_label=authored_label,
        application_label=application_label,
        raw_name=raw_name,
        raw_tooltip=_mapping_text(metadata, "tooltip"),
    )


def _output_requests(
    live_definition: Mapping[str, object],
) -> tuple[NodeFieldPresentationRequest, ...]:
    """Capture raw output names by stable Comfy slot for catalog projection."""

    type_names = _text_sequence(live_definition.get("output"))
    output_names = _text_sequence(live_definition.get("output_name"))
    output_count = max(len(type_names), len(output_names))
    return tuple(
        NodeFieldPresentationRequest(
            field_key=str(slot),
            raw_name=(
                output_names[slot]
                if slot < len(output_names)
                else type_names[slot]
                if slot < len(type_names)
                else None
            ),
        )
        for slot in range(output_count)
    )


def _text_sequence(value: object) -> tuple[str, ...]:
    """Return only text members from an untrusted live-definition sequence."""

    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _mapping_text(mapping: Mapping[str, object], key: str) -> str | None:
    """Read one optional nonempty string from untrusted definition metadata."""

    value = mapping.get(key)
    return _clean_text(value) if isinstance(value, str) else None


def _clean_text(value: str | None) -> str | None:
    """Strip presentation metadata while preserving its Unicode content."""

    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


__all__ = ["build_node_presentation_request", "present_node_card"]
