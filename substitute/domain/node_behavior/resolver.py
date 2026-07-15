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

"""Resolve layered node behavior into one typed contract per node instance."""

from __future__ import annotations

from .defaults import host_field_behavior_patch, host_node_behavior_patch
from .common_field_groups import infer_common_field_groups
from .dimension_fields import infer_dimension_field_groups
from .inference import infer_node_behavior_patch
from .models import (
    ActivationSwitchSource,
    CardBehavior,
    CardBehaviorPatch,
    FieldBehavior,
    FieldBehaviorPatch,
    NodeBehaviorContext,
    NodeBehaviorPatch,
    OverrideBehavior,
    OverrideBehaviorPatch,
    PromptFieldBehavior,
    PromptFieldBehaviorPatch,
    ResolvedNodeBehavior,
)


def _default_card_behavior() -> CardBehavior:
    """Return the empty base card behavior."""

    return CardBehavior()


def _default_field_behavior(field_key: str) -> FieldBehavior:
    """Return the empty base field behavior for one field."""

    return FieldBehavior(field_key=field_key)


def _merge_override_behavior_patches(
    *patches: OverrideBehaviorPatch,
) -> OverrideBehaviorPatch:
    """Return one override patch created by overlaying later patches over earlier ones."""

    override_key = None
    pin_policy = None
    toolbar_label_override = None
    toolbar_order = None
    for patch in patches:
        if patch.override_key is not None:
            override_key = patch.override_key
        if patch.pin_policy is not None:
            pin_policy = patch.pin_policy
        if patch.toolbar_label_override is not None:
            toolbar_label_override = patch.toolbar_label_override
        if patch.toolbar_order is not None:
            toolbar_order = patch.toolbar_order
    return OverrideBehaviorPatch(
        override_key=override_key,
        pin_policy=pin_policy,
        toolbar_label_override=toolbar_label_override,
        toolbar_order=toolbar_order,
    )


def _merge_prompt_field_behavior_patches(
    *patches: PromptFieldBehaviorPatch,
) -> PromptFieldBehaviorPatch:
    """Return one prompt patch created by overlaying later patches over earlier ones."""

    role = None
    linkable = None
    for patch in patches:
        if patch.role is not None:
            role = patch.role
        if patch.linkable is not None:
            linkable = patch.linkable
    return PromptFieldBehaviorPatch(role=role, linkable=linkable)


def merge_field_behavior_patches(
    *patches: FieldBehaviorPatch,
) -> FieldBehaviorPatch:
    """Return one field patch created by overlaying later patches over earlier ones."""

    presentation = None
    control_name = None
    row_mode = None
    label_mode = None
    label_override = None
    column_span = None
    style = None
    hidden = None
    override_behavior = None
    prompt = None
    for patch in patches:
        if patch.presentation is not None:
            presentation = patch.presentation
        if patch.control_name is not None:
            control_name = patch.control_name
        if patch.row_mode is not None:
            row_mode = patch.row_mode
        if patch.label_mode is not None:
            label_mode = patch.label_mode
        if patch.label_override is not None:
            label_override = patch.label_override
        if patch.column_span is not None:
            column_span = patch.column_span
        if patch.style is not None:
            style = dict(patch.style)
        if patch.hidden is not None:
            hidden = patch.hidden
        if patch.override_behavior is not None:
            override_behavior = _merge_override_behavior_patches(
                override_behavior or OverrideBehaviorPatch(),
                patch.override_behavior,
            )
        if patch.prompt is not None:
            prompt = _merge_prompt_field_behavior_patches(
                prompt or PromptFieldBehaviorPatch(),
                patch.prompt,
            )
    return FieldBehaviorPatch(
        presentation=presentation,
        control_name=control_name,
        row_mode=row_mode,
        label_mode=label_mode,
        label_override=label_override,
        column_span=column_span,
        style=style,
        hidden=hidden,
        override_behavior=override_behavior,
        prompt=prompt,
    )


def merge_card_behavior_patches(*patches: CardBehaviorPatch) -> CardBehaviorPatch:
    """Return one card patch created by overlaying later patches over earlier ones."""

    card_mode = None
    collapse_mode = None
    enabled_switch_policy = None
    enabled_switch_source = None
    activation_switch_role = None
    activation_signal_types = None
    activation_default = None
    visibility_rule = None
    reveal_mode = None
    icon_name = None
    title_controls = None
    hidden = None
    force_visible = None
    for patch in patches:
        if patch.card_mode is not None:
            card_mode = patch.card_mode
        if patch.collapse_mode is not None:
            collapse_mode = patch.collapse_mode
        if patch.enabled_switch_policy is not None:
            enabled_switch_policy = patch.enabled_switch_policy
        if patch.enabled_switch_source is not None:
            enabled_switch_source = patch.enabled_switch_source
        if patch.activation_switch_role is not None:
            activation_switch_role = patch.activation_switch_role
        if patch.activation_signal_types is not None:
            activation_signal_types = frozenset(patch.activation_signal_types)
        if patch.activation_default is not None:
            activation_default = patch.activation_default
        if patch.visibility_rule is not None:
            visibility_rule = patch.visibility_rule
        if patch.reveal_mode is not None:
            reveal_mode = patch.reveal_mode
        if patch.icon_name is not None:
            icon_name = patch.icon_name
        if patch.title_controls is not None:
            title_controls = tuple(patch.title_controls)
        if patch.hidden is not None:
            hidden = patch.hidden
        if patch.force_visible is not None:
            force_visible = patch.force_visible
    return CardBehaviorPatch(
        card_mode=card_mode,
        collapse_mode=collapse_mode,
        enabled_switch_policy=enabled_switch_policy,
        enabled_switch_source=enabled_switch_source,
        activation_switch_role=activation_switch_role,
        activation_signal_types=activation_signal_types,
        activation_default=activation_default,
        visibility_rule=visibility_rule,
        reveal_mode=reveal_mode,
        icon_name=icon_name,
        title_controls=title_controls,
        hidden=hidden,
        force_visible=force_visible,
    )


def _patch_with_enabled_switch_source(
    patch: NodeBehaviorPatch,
    source: ActivationSwitchSource,
) -> NodeBehaviorPatch:
    """Return a patch with source attached to authored switch-policy changes."""

    if (
        patch.card.enabled_switch_policy is None
        or patch.card.enabled_switch_source is not None
    ):
        return patch
    return NodeBehaviorPatch(
        card=CardBehaviorPatch(
            card_mode=patch.card.card_mode,
            collapse_mode=patch.card.collapse_mode,
            enabled_switch_policy=patch.card.enabled_switch_policy,
            enabled_switch_source=source,
            activation_switch_role=patch.card.activation_switch_role,
            activation_signal_types=patch.card.activation_signal_types,
            activation_default=patch.card.activation_default,
            visibility_rule=patch.card.visibility_rule,
            reveal_mode=patch.card.reveal_mode,
            icon_name=patch.card.icon_name,
            title_controls=patch.card.title_controls,
            hidden=patch.card.hidden,
            force_visible=patch.card.force_visible,
        ),
        field_patches=patch.field_patches,
        field_groups=patch.field_groups,
    )


def merge_node_behavior_patches(*patches: NodeBehaviorPatch) -> NodeBehaviorPatch:
    """Return one node patch created by overlaying later patches over earlier ones."""

    merged_card = merge_card_behavior_patches(*(patch.card for patch in patches))
    merged_groups = None
    merged_fields: dict[str, FieldBehaviorPatch] = {}
    for patch in patches:
        if patch.field_groups is not None:
            merged_groups = tuple(tuple(group) for group in patch.field_groups)
        for field_key, field_patch in patch.field_patches.items():
            merged_fields[field_key] = merge_field_behavior_patches(
                merged_fields.get(field_key, FieldBehaviorPatch()),
                field_patch,
            )
    return NodeBehaviorPatch(
        card=merged_card,
        field_patches=merged_fields,
        field_groups=merged_groups,
    )


def _package_field_group_patches(
    package_patch: object,
    *,
    class_type: str,
    node_name: str,
    node_instance_key: str,
) -> tuple[NodeBehaviorPatch, ...]:
    """Return authored node patches that can explicitly control field groups."""

    if package_patch is None:
        return ()
    patches: list[NodeBehaviorPatch] = []
    for patch in (
        getattr(package_patch, "by_class", {}).get(class_type),
        getattr(package_patch, "by_node", {}).get(node_name),
        getattr(package_patch, "by_node_instance", {}).get(node_instance_key),
    ):
        if isinstance(patch, NodeBehaviorPatch):
            patches.append(patch)
    return tuple(patches)


def _has_authoritative_field_group_override(
    *,
    context: NodeBehaviorContext,
    class_type: str,
    node_name: str,
    node_instance_key: str,
) -> bool:
    """Return whether authored behavior explicitly controls field groups."""

    authored_patches = (
        *_package_field_group_patches(
            context.declarative_patch,
            class_type=class_type,
            node_name=node_name,
            node_instance_key=node_instance_key,
        ),
        *_package_field_group_patches(
            context.hook_patch,
            class_type=class_type,
            node_name=node_name,
            node_instance_key=node_instance_key,
        ),
        *(
            (context.node_instance_patch,)
            if context.node_instance_patch is not None
            else ()
        ),
    )
    return any(patch.field_groups is not None for patch in authored_patches)


def _occupied_group_fields(field_groups: tuple[tuple[str, ...], ...]) -> frozenset[str]:
    """Return all fields already claimed by resolved field groups."""

    return frozenset(field_key for group in field_groups for field_key in group)


def _append_inferred_groups(
    *,
    input_keys: tuple[str, ...],
    base_groups: tuple[tuple[str, ...], ...],
) -> tuple[tuple[str, ...], ...]:
    """Append non-conflicting inferred common and dimension groups after base groups."""

    common_groups = infer_common_field_groups(
        input_keys,
        occupied_fields=_occupied_group_fields(base_groups),
    )
    dimension_groups = infer_dimension_field_groups(
        input_keys,
        occupied_fields=_occupied_group_fields((*base_groups, *common_groups)),
    )
    if not common_groups and not dimension_groups:
        return base_groups
    return (*base_groups, *common_groups, *dimension_groups)


def _resolve_field_groups(
    *,
    input_keys: tuple[str, ...],
    merged_patch: NodeBehaviorPatch,
    context: NodeBehaviorContext,
    class_type: str,
    node_name: str,
    node_instance_key: str,
) -> tuple[tuple[str, ...], ...]:
    """Return final field groups after authored overrides and dimension inference."""

    base_groups = tuple(tuple(group) for group in (merged_patch.field_groups or ()))
    if _has_authoritative_field_group_override(
        context=context,
        class_type=class_type,
        node_name=node_name,
        node_instance_key=node_instance_key,
    ):
        return base_groups
    return _append_inferred_groups(
        input_keys=input_keys,
        base_groups=base_groups,
    )


def _apply_card_patch(base: CardBehavior, patch: CardBehaviorPatch) -> CardBehavior:
    """Return resolved card behavior by applying a patch to a base value."""

    return CardBehavior(
        card_mode=patch.card_mode or base.card_mode,
        collapse_mode=patch.collapse_mode or base.collapse_mode,
        enabled_switch_policy=(
            patch.enabled_switch_policy or base.enabled_switch_policy
        ),
        enabled_switch_source=(
            patch.enabled_switch_source or base.enabled_switch_source
        ),
        activation_switch_role=(
            patch.activation_switch_role or base.activation_switch_role
        ),
        activation_signal_types=(
            patch.activation_signal_types
            if patch.activation_signal_types is not None
            else base.activation_signal_types
        ),
        activation_default=patch.activation_default or base.activation_default,
        visibility_rule=patch.visibility_rule or base.visibility_rule,
        reveal_mode=patch.reveal_mode or base.reveal_mode,
        icon_name=patch.icon_name if patch.icon_name is not None else base.icon_name,
        title_controls=(
            tuple(patch.title_controls)
            if patch.title_controls is not None
            else tuple(base.title_controls)
        ),
        hidden=patch.hidden if patch.hidden is not None else base.hidden,
        force_visible=(
            patch.force_visible
            if patch.force_visible is not None
            else base.force_visible
        ),
        tooltip=base.tooltip,
    )


def _apply_field_patch(base: FieldBehavior, patch: FieldBehaviorPatch) -> FieldBehavior:
    """Return resolved field behavior by applying a patch to a base value."""

    prompt = base.prompt
    if patch.prompt is not None:
        role = (
            patch.prompt.role
            if patch.prompt.role is not None
            else (base.prompt.role if base.prompt is not None else None)
        )
        if role is not None:
            linkable = (
                patch.prompt.linkable
                if patch.prompt.linkable is not None
                else (base.prompt.linkable if base.prompt is not None else True)
            )
            prompt = PromptFieldBehavior(role=role, linkable=linkable)

    return FieldBehavior(
        field_key=base.field_key,
        presentation=patch.presentation or base.presentation,
        control_name=(
            patch.control_name if patch.control_name is not None else base.control_name
        ),
        row_mode=patch.row_mode or base.row_mode,
        label_mode=patch.label_mode or base.label_mode,
        label_override=(
            patch.label_override
            if patch.label_override is not None
            else base.label_override
        ),
        column_span=(
            patch.column_span if patch.column_span is not None else base.column_span
        ),
        style=dict(patch.style) if patch.style is not None else dict(base.style),
        hidden=patch.hidden if patch.hidden is not None else base.hidden,
        override_behavior=OverrideBehavior(
            override_key=(
                patch.override_behavior.override_key
                if patch.override_behavior is not None
                and patch.override_behavior.override_key is not None
                else base.override_behavior.override_key
            ),
            pin_policy=(
                patch.override_behavior.pin_policy
                if patch.override_behavior is not None
                and patch.override_behavior.pin_policy is not None
                else base.override_behavior.pin_policy
            ),
            toolbar_label_override=(
                patch.override_behavior.toolbar_label_override
                if patch.override_behavior is not None
                and patch.override_behavior.toolbar_label_override is not None
                else base.override_behavior.toolbar_label_override
            ),
            toolbar_order=(
                patch.override_behavior.toolbar_order
                if patch.override_behavior is not None
                and patch.override_behavior.toolbar_order is not None
                else base.override_behavior.toolbar_order
            ),
        ),
        prompt=prompt,
    )


def resolve_node_behavior(
    *,
    node_name: str,
    class_type: str,
    input_keys: tuple[str, ...],
    context: NodeBehaviorContext,
) -> ResolvedNodeBehavior:
    """Resolve layered behavior for one node instance."""

    node_instance_key = f"{context.cube_alias}:{node_name}"
    merged_patch = merge_node_behavior_patches(
        _patch_with_enabled_switch_source(
            host_node_behavior_patch(node_name, class_type),
            ActivationSwitchSource.HOST,
        ),
        infer_node_behavior_patch(
            context.live_node_definition,
            node_title=context.node_title,
            input_keys=input_keys,
        ),
        _patch_with_enabled_switch_source(
            (
                context.declarative_patch.by_class.get(class_type, NodeBehaviorPatch())
                if context.declarative_patch is not None
                else NodeBehaviorPatch()
            ),
            ActivationSwitchSource.DECLARATIVE,
        ),
        _patch_with_enabled_switch_source(
            (
                context.declarative_patch.by_node.get(node_name, NodeBehaviorPatch())
                if context.declarative_patch is not None
                else NodeBehaviorPatch()
            ),
            ActivationSwitchSource.DECLARATIVE,
        ),
        _patch_with_enabled_switch_source(
            (
                context.declarative_patch.by_node_instance.get(
                    node_instance_key,
                    NodeBehaviorPatch(),
                )
                if context.declarative_patch is not None
                else NodeBehaviorPatch()
            ),
            ActivationSwitchSource.DECLARATIVE,
        ),
        _patch_with_enabled_switch_source(
            (
                context.hook_patch.by_class.get(class_type, NodeBehaviorPatch())
                if context.hook_patch is not None
                else NodeBehaviorPatch()
            ),
            ActivationSwitchSource.HOOK,
        ),
        _patch_with_enabled_switch_source(
            (
                context.hook_patch.by_node.get(node_name, NodeBehaviorPatch())
                if context.hook_patch is not None
                else NodeBehaviorPatch()
            ),
            ActivationSwitchSource.HOOK,
        ),
        _patch_with_enabled_switch_source(
            (
                context.hook_patch.by_node_instance.get(
                    node_instance_key, NodeBehaviorPatch()
                )
                if context.hook_patch is not None
                else NodeBehaviorPatch()
            ),
            ActivationSwitchSource.HOOK,
        ),
        _patch_with_enabled_switch_source(
            context.node_instance_patch or NodeBehaviorPatch(),
            ActivationSwitchSource.RUNTIME,
        ),
    )

    card = _apply_card_patch(_default_card_behavior(), merged_patch.card)
    fields: dict[str, FieldBehavior] = {}
    for field_key in input_keys:
        fields[field_key] = _apply_field_patch(
            _apply_field_patch(
                _default_field_behavior(field_key),
                host_field_behavior_patch(field_key),
            ),
            merged_patch.field_patches.get(field_key, FieldBehaviorPatch()),
        )
        if (
            context.declarative_patch is not None
            and field_key
            in context.declarative_patch.hidden_fields_by_node.get(
                node_name, frozenset()
            )
        ) or (
            context.hook_patch is not None
            and field_key
            in context.hook_patch.hidden_fields_by_node.get(node_name, frozenset())
        ):
            field_behavior = fields[field_key]
            fields[field_key] = FieldBehavior(
                field_key=field_behavior.field_key,
                presentation=field_behavior.presentation,
                control_name=field_behavior.control_name,
                row_mode=field_behavior.row_mode,
                label_mode=field_behavior.label_mode,
                label_override=field_behavior.label_override,
                column_span=field_behavior.column_span,
                style=field_behavior.style,
                hidden=True,
                override_behavior=field_behavior.override_behavior,
                prompt=field_behavior.prompt,
            )

    return ResolvedNodeBehavior(
        node_name=node_name,
        class_type=class_type,
        card=card,
        fields=fields,
        field_groups=_resolve_field_groups(
            input_keys=input_keys,
            merged_patch=merged_patch,
            context=context,
            class_type=class_type,
            node_name=node_name,
            node_instance_key=node_instance_key,
        ),
    )


__all__ = [
    "merge_card_behavior_patches",
    "merge_field_behavior_patches",
    "merge_node_behavior_patches",
    "resolve_node_behavior",
]
