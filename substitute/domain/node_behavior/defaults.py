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

"""Define built-in host node-behavior defaults for standalone cubes."""

from __future__ import annotations

from typing import Final

from .models import (
    ActivationDefault,
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
    PromptFieldBehaviorPatch,
    PromptRole,
    RowMode,
    TitleControl,
)


_PROMPT_NODE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "positive_prompt",
        "negative_prompt",
    }
)

_NODE_DEFAULTS: Final[dict[str, NodeBehaviorPatch]] = {
    "positive_prompt": NodeBehaviorPatch(
        card=CardBehaviorPatch(
            card_mode=CardMode.PROMPT,
            collapse_mode=CollapseMode.EXEMPT,
            icon_name="edit",
            title_controls=(TitleControl.NODE_LINK_SELECTOR,),
        ),
        field_patches={
            "prompt_template": FieldBehaviorPatch(
                presentation=FieldPresentation.PROMPT_BOX,
                row_mode=RowMode.FULL_WIDTH,
                label_mode=LabelMode.PROMPT,
                style={"prompt_syntaxes": ["emphasis", "wildcard", "lora"]},
                prompt=PromptFieldBehaviorPatch(role=PromptRole.POSITIVE),
            )
        },
    ),
    "negative_prompt": NodeBehaviorPatch(
        card=CardBehaviorPatch(
            card_mode=CardMode.PROMPT,
            collapse_mode=CollapseMode.EXEMPT,
            icon_name="eraser",
            title_controls=(TitleControl.NODE_LINK_SELECTOR,),
        ),
        field_patches={
            "prompt_template": FieldBehaviorPatch(
                presentation=FieldPresentation.PROMPT_BOX,
                row_mode=RowMode.FULL_WIDTH,
                label_mode=LabelMode.PROMPT,
                style={"prompt_syntaxes": ["emphasis", "wildcard", "lora"]},
                prompt=PromptFieldBehaviorPatch(role=PromptRole.NEGATIVE),
            )
        },
    ),
}

_CLASS_DEFAULTS: Final[dict[str, NodeBehaviorPatch]] = {
    "LoadImage": NodeBehaviorPatch(
        card=CardBehaviorPatch(icon_name="folder"),
        field_patches={
            "image": FieldBehaviorPatch(
                presentation=FieldPresentation.IMAGE_PICKER,
                row_mode=RowMode.FULL_WIDTH,
                label_mode=LabelMode.HIDDEN,
            )
        },
    ),
    "LoadImageMask": NodeBehaviorPatch(
        card=CardBehaviorPatch(icon_name="folder"),
        field_patches={
            "image": FieldBehaviorPatch(
                presentation=FieldPresentation.MASK_PICKER,
                row_mode=RowMode.FULL_WIDTH,
                label_mode=LabelMode.HIDDEN,
            )
        },
    ),
    "EmptyLatentImage": NodeBehaviorPatch(
        card=CardBehaviorPatch(icon_name="photo"),
    ),
    "KSampler": NodeBehaviorPatch(
        card=CardBehaviorPatch(
            icon_name="application",
            enabled_switch_policy=EnabledSwitchPolicy.NEVER,
            enabled_switch_source=ActivationSwitchSource.HOST,
        ),
    ),
    "DetailerForEach": NodeBehaviorPatch(
        card=CardBehaviorPatch(icon_name="application")
    ),
    "SimpleSyrup.PromptEncodeStyle": NodeBehaviorPatch(
        card=CardBehaviorPatch(icon_name="edit"),
        field_patches={
            "encode_style": FieldBehaviorPatch(
                override_behavior=OverrideBehaviorPatch(
                    override_key="encode_style",
                    pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                    toolbar_label_override="Encode Style",
                    toolbar_order=10,
                )
            )
        },
    ),
    "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl": NodeBehaviorPatch(
        card=CardBehaviorPatch(
            activation_default=ActivationDefault.ENABLED,
            enabled_switch_policy=EnabledSwitchPolicy.NEVER,
            hidden=True,
        ),
    ),
    "VectorscopeCC": NodeBehaviorPatch(
        card=CardBehaviorPatch(
            icon_name="palette",
            enabled_switch_policy=EnabledSwitchPolicy.ALWAYS,
            enabled_switch_source=ActivationSwitchSource.HOST,
            title_controls=(TitleControl.NODE_LINK_SELECTOR,),
        ),
        field_groups=(("method", "scaling"),),
        field_patches={
            "brightness": FieldBehaviorPatch(
                presentation=FieldPresentation.CUSTOM,
                control_name="color_slider",
                style={"start": "#000000", "end": "#ffffff"},
            ),
            "contrast": FieldBehaviorPatch(
                presentation=FieldPresentation.CUSTOM,
                control_name="color_slider",
                style={"start": "#777777", "end": "#ffffff"},
            ),
            "saturation": FieldBehaviorPatch(
                presentation=FieldPresentation.CUSTOM,
                control_name="color_slider",
                style={"start": "#808080", "end": "#ff00ff"},
            ),
            "r": FieldBehaviorPatch(
                presentation=FieldPresentation.CUSTOM,
                control_name="color_slider",
                label_override="Red",
                style={"start": "#00ffff", "end": "#ff0000"},
            ),
            "g": FieldBehaviorPatch(
                presentation=FieldPresentation.CUSTOM,
                control_name="color_slider",
                label_override="Green",
                style={"start": "#ff00ff", "end": "#00ff00"},
            ),
            "b": FieldBehaviorPatch(
                presentation=FieldPresentation.CUSTOM,
                control_name="color_slider",
                label_override="Blue",
                style={"start": "#ffff00", "end": "#0000ff"},
            ),
        },
    ),
    "VAELoader": NodeBehaviorPatch(
        card=CardBehaviorPatch(
            icon_name="model",
            enabled_switch_policy=EnabledSwitchPolicy.ALWAYS,
            enabled_switch_source=ActivationSwitchSource.HOST,
        )
    ),
    "CheckpointLoaderSimple": NodeBehaviorPatch(
        card=CardBehaviorPatch(
            icon_name="model",
        )
    ),
}

_FIELD_DEFAULTS: Final[dict[str, FieldBehaviorPatch]] = {
    "seed": FieldBehaviorPatch(
        override_behavior=OverrideBehaviorPatch(
            override_key="seed",
            pin_policy=OverridePinPolicy.DEFAULT_PINNED,
            toolbar_order=60,
        )
    ),
    "sampler_name": FieldBehaviorPatch(
        override_behavior=OverrideBehaviorPatch(
            override_key="sampler_name",
            pin_policy=OverridePinPolicy.DEFAULT_PINNED,
            toolbar_label_override="Sampler",
            toolbar_order=20,
        )
    ),
    "scheduler": FieldBehaviorPatch(
        override_behavior=OverrideBehaviorPatch(
            override_key="scheduler",
            pin_policy=OverridePinPolicy.DEFAULT_PINNED,
            toolbar_order=30,
        )
    ),
    "steps": FieldBehaviorPatch(
        override_behavior=OverrideBehaviorPatch(
            override_key="steps",
            pin_policy=OverridePinPolicy.OPTIONAL,
            toolbar_order=40,
        )
    ),
    "cfg": FieldBehaviorPatch(
        override_behavior=OverrideBehaviorPatch(
            override_key="cfg",
            pin_policy=OverridePinPolicy.OPTIONAL,
            toolbar_label_override="CFG",
            toolbar_order=50,
        )
    ),
}


def _merge_node_patch_layers(
    *,
    primary: NodeBehaviorPatch,
    secondary: NodeBehaviorPatch,
) -> NodeBehaviorPatch:
    """Overlay a node-specific patch onto a class-specific patch."""

    return NodeBehaviorPatch(
        card=CardBehaviorPatch(
            card_mode=(
                primary.card.card_mode
                if primary.card.card_mode is not None
                else secondary.card.card_mode
            ),
            collapse_mode=(
                primary.card.collapse_mode
                if primary.card.collapse_mode is not None
                else secondary.card.collapse_mode
            ),
            enabled_switch_policy=(
                primary.card.enabled_switch_policy
                if primary.card.enabled_switch_policy is not None
                else secondary.card.enabled_switch_policy
            ),
            enabled_switch_source=(
                primary.card.enabled_switch_source
                if primary.card.enabled_switch_source is not None
                else secondary.card.enabled_switch_source
            ),
            activation_switch_role=(
                primary.card.activation_switch_role
                if primary.card.activation_switch_role is not None
                else secondary.card.activation_switch_role
            ),
            activation_signal_types=(
                primary.card.activation_signal_types
                if primary.card.activation_signal_types is not None
                else secondary.card.activation_signal_types
            ),
            visibility_rule=(
                primary.card.visibility_rule
                if primary.card.visibility_rule is not None
                else secondary.card.visibility_rule
            ),
            reveal_mode=(
                primary.card.reveal_mode
                if primary.card.reveal_mode is not None
                else secondary.card.reveal_mode
            ),
            icon_name=primary.card.icon_name or secondary.card.icon_name,
            title_controls=(
                primary.card.title_controls
                if primary.card.title_controls is not None
                else secondary.card.title_controls
            ),
            hidden=(
                primary.card.hidden
                if primary.card.hidden is not None
                else secondary.card.hidden
            ),
            force_visible=(
                primary.card.force_visible
                if primary.card.force_visible is not None
                else secondary.card.force_visible
            ),
        ),
        field_patches={
            **secondary.field_patches,
            **primary.field_patches,
        },
        field_groups=(
            primary.field_groups
            if primary.field_groups is not None
            else secondary.field_groups
        ),
    )


def host_node_behavior_patch(node_name: str, class_type: str) -> NodeBehaviorPatch:
    """Return the built-in behavior patch for one node instance."""

    node_patch = _NODE_DEFAULTS.get(node_name)
    class_patch = _CLASS_DEFAULTS.get(class_type)
    if node_patch is not None and class_patch is None:
        return node_patch
    if node_patch is None and class_patch is not None:
        return class_patch
    if node_patch is None and class_patch is None:
        return NodeBehaviorPatch()
    assert node_patch is not None
    assert class_patch is not None
    return _merge_node_patch_layers(primary=node_patch, secondary=class_patch)


def host_field_behavior_patch(field_key: str) -> FieldBehaviorPatch:
    """Return the built-in field behavior patch for one input key."""

    return _FIELD_DEFAULTS.get(field_key, FieldBehaviorPatch())


def is_prompt_node_name(node_name: str) -> bool:
    """Return whether the node name is one of the built-in prompt aliases."""

    return node_name in _PROMPT_NODE_NAMES


__all__ = [
    "host_field_behavior_patch",
    "host_node_behavior_patch",
    "is_prompt_node_name",
]
