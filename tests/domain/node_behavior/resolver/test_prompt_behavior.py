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

"""Verify prompt behavior inference and precedence."""

from __future__ import annotations

from substitute.domain.node_behavior import (
    CardMode,
    CollapseMode,
    FieldBehaviorPatch,
    FieldPresentation,
    LabelMode,
    NodeBehaviorPatch,
    NodeBehaviorContext,
    PackageBehaviorPatch,
    PromptFieldBehaviorPatch,
    PromptRole,
    RowMode,
    TitleControl,
    resolve_node_behavior,
)
from substitute.domain.node_behavior.prompt_behavior_patch import (
    prompt_node_behavior_patch,
)
from tests.domain.node_behavior.resolver.support import context


def test_resolver_keeps_prompt_field_syntax_style_on_builtin_prompt_nodes() -> None:
    """Built-in prompt nodes should opt prompt_template into emphasis and wildcard rendering."""

    context = NodeBehaviorContext(
        stack_order=("A",),
        cube_alias="A",
        node_name="positive_prompt",
        class_type="Whatever",
        node_title=None,
        live_node_definition=None,
        declarative_patch=None,
        hook_patch=None,
        workflow_overrides={},
        node_instance_patch=None,
    )

    resolved = resolve_node_behavior(
        node_name="positive_prompt",
        class_type="Whatever",
        input_keys=("prompt_template",),
        context=context,
    )

    assert resolved.fields["prompt_template"].style == {
        "prompt_syntaxes": ["emphasis", "wildcard", "lora"]
    }
    assert resolved.fields["prompt_template"].prompt is not None
    assert resolved.fields["prompt_template"].prompt.role == PromptRole.POSITIVE


def test_resolver_merges_prompt_field_behavior_with_later_layer_precedence() -> None:
    """Later layers should override prompt role metadata without changing presentation."""

    declarative = PackageBehaviorPatch(
        by_node={
            "prompt": NodeBehaviorPatch(
                field_patches={
                    "text": FieldBehaviorPatch(
                        presentation=FieldPresentation.PROMPT_BOX,
                        prompt=PromptFieldBehaviorPatch(role=PromptRole.POSITIVE),
                    )
                }
            )
        }
    )
    runtime = NodeBehaviorPatch(
        field_patches={
            "text": FieldBehaviorPatch(
                prompt=PromptFieldBehaviorPatch(
                    role=PromptRole.NEGATIVE,
                    linkable=False,
                )
            )
        }
    )
    context = NodeBehaviorContext(
        stack_order=("A",),
        cube_alias="A",
        node_name="prompt",
        class_type="PromptNode",
        node_title=None,
        live_node_definition=None,
        declarative_patch=declarative,
        hook_patch=None,
        workflow_overrides={},
        node_instance_patch=runtime,
    )

    resolved = resolve_node_behavior(
        node_name="prompt",
        class_type="PromptNode",
        input_keys=("text",),
        context=context,
    )

    prompt = resolved.fields["text"].prompt
    assert resolved.fields["text"].presentation == FieldPresentation.PROMPT_BOX
    assert prompt is not None
    assert prompt.role == PromptRole.NEGATIVE
    assert prompt.linkable is False
    assert resolved.card.card_mode == CardMode.STANDARD
    assert resolved.card.collapse_mode == CollapseMode.AUTO


def test_resolver_does_not_promote_card_mode_from_prompt_box_field() -> None:
    """Prompt field presentation should not make a whole node a prompt card."""

    runtime = NodeBehaviorPatch(
        field_patches={
            "positive_prompt": FieldBehaviorPatch(
                presentation=FieldPresentation.PROMPT_BOX,
                prompt=PromptFieldBehaviorPatch(role=PromptRole.POSITIVE),
            ),
        }
    )

    resolved = resolve_node_behavior(
        node_name="schedule",
        class_type="SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl",
        input_keys=("positive_prompt", "encode_style"),
        context=context(
            node_name="schedule",
            class_type="SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl",
            runtime_patch=runtime,
        ),
    )

    assert resolved.fields["positive_prompt"].presentation == (
        FieldPresentation.PROMPT_BOX
    )
    assert resolved.card.card_mode == CardMode.STANDARD
    assert resolved.card.collapse_mode == CollapseMode.AUTO


def test_resolver_applies_graph_inferred_positive_prompt_patch() -> None:
    """Prepared graph inference should become existing linkable prompt behavior."""

    context = NodeBehaviorContext(
        stack_order=("A",),
        cube_alias="A",
        node_name="node_17",
        class_type="CustomPrompt",
        node_title="Positive Prompt",
        live_node_definition={
            "input": {
                "required": {
                    "text": ["STRING", {"multiline": True}],
                }
            }
        },
        declarative_patch=None,
        hook_patch=None,
        workflow_overrides={},
        node_instance_patch=None,
        graph_inference_patch=prompt_node_behavior_patch(
            field_key="text",
            role=PromptRole.POSITIVE,
        ),
    )

    resolved = resolve_node_behavior(
        node_name="node_17",
        class_type="CustomPrompt",
        input_keys=("text",),
        context=context,
    )

    field = resolved.fields["text"]
    assert field.presentation == FieldPresentation.PROMPT_BOX
    assert field.row_mode == RowMode.FULL_WIDTH
    assert field.label_mode == LabelMode.PROMPT
    assert field.prompt is not None
    assert field.prompt.role == PromptRole.POSITIVE
    assert resolved.card.card_mode == CardMode.PROMPT
    assert resolved.card.collapse_mode == CollapseMode.EXEMPT
    assert resolved.card.icon_name == "edit"
    assert resolved.card.title_controls == (TitleControl.NODE_LINK_SELECTOR,)


def test_resolver_applies_graph_inferred_negative_prompt_icon() -> None:
    """Prepared negative prompt behavior should use the eraser icon."""

    context = NodeBehaviorContext(
        stack_order=("A",),
        cube_alias="A",
        node_name="node_18",
        class_type="CustomPrompt",
        node_title="Negative Prompt",
        live_node_definition={
            "input": {
                "required": {
                    "text": ["STRING", {"multiline": True}],
                }
            }
        },
        declarative_patch=None,
        hook_patch=None,
        workflow_overrides={},
        node_instance_patch=None,
        graph_inference_patch=prompt_node_behavior_patch(
            field_key="text",
            role=PromptRole.NEGATIVE,
        ),
    )

    resolved = resolve_node_behavior(
        node_name="node_18",
        class_type="CustomPrompt",
        input_keys=("text",),
        context=context,
    )

    assert resolved.fields["text"].prompt is not None
    assert resolved.fields["text"].prompt.role == PromptRole.NEGATIVE
    assert resolved.card.icon_name == "eraser"


def test_authored_prompt_behavior_overrides_graph_inference() -> None:
    """Declarative package behavior must remain authoritative over graph evidence."""

    context = NodeBehaviorContext(
        stack_order=("A",),
        cube_alias="A",
        node_name="encoder",
        class_type="CustomEncoder",
        node_title="Encoder",
        live_node_definition={
            "input": {"required": {"text": ["STRING", {"multiline": True}]}}
        },
        declarative_patch=PackageBehaviorPatch(
            by_node={
                "encoder": prompt_node_behavior_patch(
                    field_key="text",
                    role=PromptRole.NEGATIVE,
                )
            }
        ),
        hook_patch=None,
        workflow_overrides={},
        node_instance_patch=None,
        graph_inference_patch=prompt_node_behavior_patch(
            field_key="text",
            role=PromptRole.POSITIVE,
        ),
    )

    resolved = resolve_node_behavior(
        node_name="encoder",
        class_type="CustomEncoder",
        input_keys=("text",),
        context=context,
    )

    assert resolved.fields["text"].prompt is not None
    assert resolved.fields["text"].prompt.role == PromptRole.NEGATIVE
    assert resolved.card.icon_name == "eraser"


def test_resolver_does_not_infer_prompt_role_from_partial_label_or_ambiguous_fields() -> (
    None
):
    """Prompt inference should require exact labels and one candidate string field."""

    partial_label = NodeBehaviorContext(
        stack_order=("A",),
        cube_alias="A",
        node_name="node_17",
        class_type="CustomPrompt",
        node_title="Positive Prompt Helper",
        live_node_definition={
            "input": {
                "required": {
                    "text": ["STRING", {"multiline": True}],
                }
            }
        },
        declarative_patch=None,
        hook_patch=None,
        workflow_overrides={},
        node_instance_patch=None,
    )
    ambiguous_fields = NodeBehaviorContext(
        stack_order=("A",),
        cube_alias="A",
        node_name="node_18",
        class_type="CustomPrompt",
        node_title="Negative Prompt",
        live_node_definition={
            "input": {
                "required": {
                    "text": ["STRING", {"multiline": True}],
                    "prefix": ["STRING", {"multiline": True}],
                }
            }
        },
        declarative_patch=None,
        hook_patch=None,
        workflow_overrides={},
        node_instance_patch=None,
    )

    partial = resolve_node_behavior(
        node_name="node_17",
        class_type="CustomPrompt",
        input_keys=("text",),
        context=partial_label,
    )
    ambiguous = resolve_node_behavior(
        node_name="node_18",
        class_type="CustomPrompt",
        input_keys=("text", "prefix"),
        context=ambiguous_fields,
    )

    assert partial.fields["text"].prompt is None
    assert partial.fields["text"].presentation == FieldPresentation.STANDARD
    assert ambiguous.fields["text"].prompt is None
    assert ambiguous.fields["prefix"].prompt is None
