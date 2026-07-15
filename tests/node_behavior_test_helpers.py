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

"""Provide shared helpers for node-behavior contract tests."""

from __future__ import annotations

from enum import StrEnum
from types import SimpleNamespace
from typing import Any, Mapping, TypeVar

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    NodeBehaviorService,
)
from substitute.domain.node_behavior import (
    ActivationDefault,
    ActivationSwitchRole,
    ActivationSwitchSource,
    CardBehaviorPatch,
    CardMode,
    CollapseMode,
    EnabledSwitchPolicy,
    FieldBehaviorPatch,
    FieldPresentation,
    LabelMode,
    NodeBehaviorPatch,
    OverrideBehaviorPatch,
    OverridePinPolicy,
    PackageBehaviorPatch,
    PromptFieldBehaviorPatch,
    PromptRole,
    RevealMode,
    RowMode,
    TitleControl,
    VisibilityRule,
)

EnumT = TypeVar("EnumT", bound=StrEnum)


def _as_bool(value: Any) -> bool | None:
    """Return bool for recognized boolean-like values, otherwise None."""

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return None


def _enum_or_none(enum_type: type[EnumT], value: object) -> EnumT | None:
    """Return enum member when the input string matches, otherwise None."""

    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError:
            return None
    return None


def _coerce_title_controls(value: object) -> tuple[TitleControl, ...] | None:
    """Return normalized title-control tuple from list-like input."""

    if not isinstance(value, list):
        return None
    controls: list[TitleControl] = []
    for item in value:
        enum_value = _enum_or_none(TitleControl, item)
        if enum_value is not None:
            controls.append(enum_value)
    return tuple(controls)


def _coerce_field_presentation(
    *,
    control_name: str | None,
    explicit_presentation: object,
) -> tuple[FieldPresentation | None, str | None]:
    """Return normalized presentation/control pairing from raw control settings."""

    presentation = _enum_or_none(FieldPresentation, explicit_presentation)
    if presentation is not None:
        return presentation, control_name
    if control_name == "prompt_box":
        return FieldPresentation.PROMPT_BOX, None
    if control_name == "image_picker":
        return FieldPresentation.IMAGE_PICKER, None
    if control_name == "mask_picker":
        return FieldPresentation.MASK_PICKER, None
    if isinstance(control_name, str) and control_name:
        return FieldPresentation.CUSTOM, control_name
    return None, None


def _decode_field_patch(raw: object) -> FieldBehaviorPatch:
    """Return one typed field patch from raw test behavior input."""

    if not isinstance(raw, Mapping):
        return FieldBehaviorPatch()
    raw_control = raw.get("control")
    control_name = raw_control if isinstance(raw_control, str) else None
    presentation, normalized_control = _coerce_field_presentation(
        control_name=control_name,
        explicit_presentation=raw.get("presentation"),
    )
    override_raw = raw.get("override")
    override_mapping = override_raw if isinstance(override_raw, Mapping) else raw
    column_span = raw.get("column_span")
    if column_span is not None:
        try:
            column_span = int(column_span)
        except (TypeError, ValueError):
            column_span = None
    raw_style = raw.get("style")
    style = None
    if isinstance(raw_style, Mapping):
        style = {
            str(style_key): style_value
            for style_key, style_value in raw_style.items()
            if isinstance(style_key, str)
        }
    raw_prompt = raw.get("prompt")
    prompt = None
    if isinstance(raw_prompt, Mapping):
        prompt_role = _enum_or_none(PromptRole, raw_prompt.get("role"))
        prompt_linkable = _as_bool(raw_prompt.get("linkable"))
        if prompt_role is not None or prompt_linkable is not None:
            prompt = PromptFieldBehaviorPatch(
                role=prompt_role,
                linkable=True if prompt_linkable is None else prompt_linkable,
            )
    return FieldBehaviorPatch(
        presentation=presentation,
        control_name=normalized_control,
        row_mode=_enum_or_none(RowMode, raw.get("row_mode")),
        label_mode=_enum_or_none(LabelMode, raw.get("label_mode")),
        label_override=raw.get("label") if isinstance(raw.get("label"), str) else None,
        column_span=column_span,
        style=style,
        hidden=_as_bool(raw.get("hidden")),
        override_behavior=OverrideBehaviorPatch(
            override_key=(
                override_mapping.get("override_key")
                if isinstance(override_mapping.get("override_key"), str)
                else None
            ),
            pin_policy=_enum_or_none(
                OverridePinPolicy,
                override_mapping.get("pin_policy"),
            ),
            toolbar_label_override=(
                override_mapping.get("toolbar_label")
                if isinstance(override_mapping.get("toolbar_label"), str)
                else (
                    override_mapping.get("toolbar_label_override")
                    if isinstance(
                        override_mapping.get("toolbar_label_override"),
                        str,
                    )
                    else None
                )
            ),
            toolbar_order=(
                int(override_mapping["toolbar_order"])
                if override_mapping.get("toolbar_order") is not None
                and str(override_mapping.get("toolbar_order"))
                .strip()
                .lstrip("-")
                .isdigit()
                else None
            ),
        ),
        prompt=prompt,
    )


def _decode_card_patch(raw: object) -> CardBehaviorPatch:
    """Return one typed card patch from raw test behavior input."""

    if not isinstance(raw, Mapping):
        return CardBehaviorPatch()
    enabled_switch_raw = raw.get("enabled_switch")
    enabled_switch_policy = _enum_or_none(
        EnabledSwitchPolicy, raw.get("enabled_switch_policy")
    )
    if enabled_switch_policy is None:
        enabled_switch = _as_bool(enabled_switch_raw)
        if enabled_switch is True:
            enabled_switch_policy = EnabledSwitchPolicy.ALWAYS
        elif enabled_switch is False:
            enabled_switch_policy = EnabledSwitchPolicy.NEVER
    raw_activation_signal_types = raw.get("activation_signal_types")
    activation_signal_types = (
        frozenset(
            str(item).strip().upper()
            for item in raw_activation_signal_types
            if isinstance(item, str) and item.strip()
        )
        if isinstance(raw_activation_signal_types, list)
        else None
    )
    return CardBehaviorPatch(
        card_mode=_enum_or_none(CardMode, raw.get("card_mode")),
        collapse_mode=_enum_or_none(CollapseMode, raw.get("collapse_mode")),
        enabled_switch_policy=enabled_switch_policy,
        enabled_switch_source=_enum_or_none(
            ActivationSwitchSource,
            raw.get("enabled_switch_source"),
        ),
        activation_switch_role=_enum_or_none(
            ActivationSwitchRole,
            raw.get("activation_switch_role"),
        ),
        activation_signal_types=activation_signal_types,
        activation_default=_enum_or_none(
            ActivationDefault,
            raw.get("activation_default"),
        ),
        visibility_rule=_enum_or_none(VisibilityRule, raw.get("visibility_rule")),
        reveal_mode=_enum_or_none(RevealMode, raw.get("reveal_mode")),
        icon_name=raw.get("icon_name")
        if isinstance(raw.get("icon_name"), str)
        else None,
        title_controls=_coerce_title_controls(raw.get("title_controls")),
        hidden=_as_bool(raw.get("hidden")),
        force_visible=_as_bool(raw.get("force_visible")),
    )


def _decode_node_patch(raw: object) -> NodeBehaviorPatch:
    """Return one typed node patch from raw test behavior input."""

    if not isinstance(raw, Mapping):
        return NodeBehaviorPatch()
    raw_groups = raw["groups"] if "groups" in raw else raw.get("field_groups")
    groups = None
    if isinstance(raw_groups, list):
        groups = tuple(
            tuple(str(item) for item in group if isinstance(item, str))
            for group in raw_groups
            if isinstance(group, list)
        )
    raw_fields = raw.get("fields")
    field_patches: dict[str, FieldBehaviorPatch] = {}
    if isinstance(raw_fields, Mapping):
        for field_key, field_payload in raw_fields.items():
            if isinstance(field_key, str):
                field_patches[field_key] = _decode_field_patch(field_payload)
    card_raw = raw.get("card") if isinstance(raw.get("card"), Mapping) else raw
    return NodeBehaviorPatch(
        card=_decode_card_patch(card_raw),
        field_patches=field_patches,
        field_groups=groups,
    )


class DummyNodeDefinitionGateway:
    """Return deterministic live node definitions for behavior tests."""

    def __init__(
        self, definitions: Mapping[str, Mapping[str, object]] | None = None
    ) -> None:
        """Store optional class-type definitions keyed by node class."""

        self._definitions = dict(definitions or {})

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one class definition in the gateway payload shape."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one required class definition in the gateway payload shape."""

        definition = self._definitions.get(node_class)
        if definition is None:
            return {}
        return {node_class: dict(definition)}


def cube_state(
    *,
    nodes: Mapping[str, object] | None = None,
    definitions: Mapping[str, object] | None = None,
    subgraphs: object | None = None,
    ui: dict[str, object] | None = None,
) -> SimpleNamespace:
    """Build a minimal cube-state double compatible with NodeBehaviorService."""

    return SimpleNamespace(
        buffer={
            "nodes": dict(nodes or {}),
            "definitions": dict(definitions or {}),
            "subgraphs": subgraphs if subgraphs is not None else [],
        },
        dirty=False,
        ui=dict(ui or {}),
    )


def bypassed_node(
    class_type: str,
    inputs: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a node payload marked with the authored Comfy bypass mode."""

    return {"class_type": class_type, "inputs": inputs or {}, "mode": 4}


def behavior_payload(raw: object) -> object:
    """Decode raw test node behavior into the canonical typed payload."""

    if not isinstance(raw, Mapping):
        return PackageBehaviorPatch()

    by_class: dict[str, NodeBehaviorPatch] = {}
    by_node: dict[str, NodeBehaviorPatch] = {}
    by_node_instance: dict[str, NodeBehaviorPatch] = {}
    hidden_strings: set[str] = set()
    hidden_class_types: set[str] = set()
    hidden_node_names: set[str] = set()
    hidden_fields_by_node: dict[str, set[str]] = {}

    hide = raw.get("hide")
    if isinstance(hide, Mapping):
        nodes = hide.get("nodes")
        if isinstance(nodes, list):
            for item in nodes:
                if isinstance(item, str):
                    hidden_strings.add(item)
                elif isinstance(item, Mapping):
                    node_name = item.get("node")
                    class_type = item.get("class") or item.get("class_type")
                    if isinstance(node_name, str):
                        hidden_node_names.add(node_name)
                    if isinstance(class_type, str):
                        hidden_class_types.add(class_type)
        fields = hide.get("fields")
        if isinstance(fields, list):
            for item in fields:
                if not isinstance(item, Mapping):
                    continue
                node_name = item.get("node")
                field_key = item.get("key")
                if isinstance(node_name, str) and isinstance(field_key, str):
                    hidden_fields_by_node.setdefault(node_name, set()).add(field_key)

    controls = raw.get("controls")
    if isinstance(controls, Mapping):
        by_class_raw = controls.get("by_class")
        if isinstance(by_class_raw, Mapping):
            for class_type, config in by_class_raw.items():
                if isinstance(class_type, str):
                    by_class[class_type] = _decode_node_patch(config)
        by_node_raw = controls.get("by_node")
        if isinstance(by_node_raw, Mapping):
            for node_name, config in by_node_raw.items():
                if isinstance(node_name, str):
                    by_node[node_name] = _decode_node_patch(config)
        by_node_instance_raw = controls.get("by_node_instance")
        if isinstance(by_node_instance_raw, Mapping):
            for instance_key, config in by_node_instance_raw.items():
                if isinstance(instance_key, str):
                    by_node_instance[instance_key] = _decode_node_patch(config)
        by_field_raw = controls.get("by_field")
        if isinstance(by_field_raw, Mapping):
            for scoped_key, config in by_field_raw.items():
                if not isinstance(scoped_key, str) or "." not in scoped_key:
                    continue
                node_name, field_key = scoped_key.split(".", 1)
                node_patch = by_node.get(node_name, NodeBehaviorPatch())
                next_fields = dict(node_patch.field_patches)
                next_fields[field_key] = _decode_field_patch(config)
                by_node[node_name] = NodeBehaviorPatch(
                    card=node_patch.card,
                    field_patches=next_fields,
                    field_groups=node_patch.field_groups,
                )

    layout = raw.get("layout")
    if isinstance(layout, Mapping):
        groups = layout.get("groups")
        if isinstance(groups, Mapping):
            for class_type, group_list in groups.items():
                if not isinstance(class_type, str):
                    continue
                decoded_patch = _decode_node_patch({"groups": group_list})
                current_patch = by_class.get(class_type, NodeBehaviorPatch())
                by_class[class_type] = NodeBehaviorPatch(
                    card=current_patch.card,
                    field_patches=current_patch.field_patches,
                    field_groups=decoded_patch.field_groups,
                )

    canonical_by_class = raw.get("by_class")
    if isinstance(canonical_by_class, Mapping):
        for class_type, config in canonical_by_class.items():
            if isinstance(class_type, str):
                by_class[class_type] = _decode_node_patch(config)

    canonical_by_node = raw.get("by_node")
    if isinstance(canonical_by_node, Mapping):
        for node_name, config in canonical_by_node.items():
            if isinstance(node_name, str):
                by_node[node_name] = _decode_node_patch(config)

    canonical_by_node_instance = raw.get("by_node_instance")
    if isinstance(canonical_by_node_instance, Mapping):
        for instance_key, config in canonical_by_node_instance.items():
            if isinstance(instance_key, str):
                by_node_instance[instance_key] = _decode_node_patch(config)

    return PackageBehaviorPatch(
        by_class=by_class,
        by_node=by_node,
        by_node_instance=by_node_instance,
        hidden_strings=frozenset(hidden_strings),
        hidden_class_types=frozenset(hidden_class_types),
        hidden_node_names=frozenset(hidden_node_names),
        hidden_fields_by_node={
            node_name: frozenset(field_keys)
            for node_name, field_keys in hidden_fields_by_node.items()
        },
    )


def build_behavior_snapshot(
    *,
    cube_states: Mapping[str, Any],
    stack_order: list[str],
    definitions_by_class: Mapping[str, Mapping[str, object]] | None = None,
    workflow_overrides: Mapping[str, object] | None = None,
    search_hidden_keys: set[object] | None = None,
    node_search_text: str | None = None,
    search_matching_nodes: set[tuple[str, str]] | None = None,
) -> EditorBehaviorSnapshot:
    """Build one editor behavior snapshot for focused test assertions."""

    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(definitions_by_class)
    )
    return service.build_snapshot(
        cube_states=cube_states,
        stack_order=stack_order,
        workflow_overrides=workflow_overrides or {},
        search_hidden_keys=search_hidden_keys,
        node_search_text=node_search_text,
        search_matching_nodes=search_matching_nodes,
    )
