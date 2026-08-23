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

"""Verify resolver layer precedence and authored ownership."""

from __future__ import annotations

from substitute.domain.node_behavior import (
    ActivationSwitchSource,
    CardBehaviorPatch,
    CardMode,
    CollapseMode,
    EnabledSwitchPolicy,
    FieldBehaviorPatch,
    FieldLabelSource,
    FieldPresentation,
    NodeBehaviorPatch,
    NodeBehaviorContext,
    PackageBehaviorPatch,
    TitleControl,
    resolve_node_behavior,
)
from tests.domain.node_behavior.resolver.support import context


def test_resolver_applies_declarative_hook_and_runtime_precedence() -> None:
    """Later node-behavior layers should override earlier layers deterministically."""

    declarative = PackageBehaviorPatch(
        by_node={
            "node": NodeBehaviorPatch(
                card=CardBehaviorPatch(card_mode=CardMode.PROMPT),
                field_patches={
                    "image": FieldBehaviorPatch(
                        presentation=FieldPresentation.IMAGE_PICKER
                    )
                },
            )
        }
    )
    hook_patch = PackageBehaviorPatch(
        by_node={
            "node": NodeBehaviorPatch(
                card=CardBehaviorPatch(
                    collapse_mode=CollapseMode.EXEMPT,
                    title_controls=(TitleControl.PROMPT_LINK_SELECTOR,),
                ),
            )
        }
    )
    runtime = NodeBehaviorPatch(
        field_patches={
            "image": FieldBehaviorPatch(presentation=FieldPresentation.MASK_PICKER)
        }
    )
    context = NodeBehaviorContext(
        stack_order=("A",),
        cube_alias="A",
        node_name="node",
        class_type="CustomNode",
        node_title=None,
        live_node_definition=None,
        declarative_patch=declarative,
        hook_patch=hook_patch,
        workflow_overrides={},
        node_instance_patch=runtime,
    )

    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("image",),
        context=context,
    )

    assert resolved.card.card_mode == CardMode.PROMPT
    assert resolved.card.collapse_mode == CollapseMode.EXEMPT
    assert resolved.card.title_controls == (TitleControl.PROMPT_LINK_SELECTOR,)
    assert resolved.fields["image"].presentation == FieldPresentation.MASK_PICKER


def test_resolver_marks_host_labels_as_application_owned() -> None:
    """Host-authored UI labels should remain eligible for application translation."""

    resolved = resolve_node_behavior(
        node_name="scope",
        class_type="VectorscopeCC",
        input_keys=("r",),
        context=context(node_name="scope", class_type="VectorscopeCC"),
    )

    red = resolved.fields["r"]
    assert red.label_override is not None
    assert red.label_override_source is FieldLabelSource.APPLICATION


def test_resolver_marks_cube_behavior_labels_as_authored() -> None:
    """Cube behavior labels should remain exact authored text in every locale."""

    declarative = PackageBehaviorPatch(
        by_node={
            "node": NodeBehaviorPatch(
                field_patches={
                    "cfg": FieldBehaviorPatch(label_override="Author's CFG Label")
                }
            )
        }
    )

    resolved = resolve_node_behavior(
        node_name="node",
        class_type="KSampler",
        input_keys=("cfg",),
        context=context(
            node_name="node",
            class_type="KSampler",
            declarative_patch=declarative,
        ),
    )

    cfg = resolved.fields["cfg"]
    assert cfg.label_override == "Author's CFG Label"
    assert cfg.label_override_source is FieldLabelSource.AUTHORED


def test_resolver_marks_authored_switch_policy_source() -> None:
    """Authored switch policies should keep provenance for engine precedence."""

    declarative = PackageBehaviorPatch(
        by_node={
            "node": NodeBehaviorPatch(
                card=CardBehaviorPatch(enabled_switch_policy=EnabledSwitchPolicy.ALWAYS)
            )
        }
    )

    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=(),
        context=context(declarative_patch=declarative),
    )

    assert resolved.card.enabled_switch_policy == EnabledSwitchPolicy.ALWAYS
    assert resolved.card.enabled_switch_source == ActivationSwitchSource.DECLARATIVE
