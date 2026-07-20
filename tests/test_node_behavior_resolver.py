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

"""Focused tests for layered node-behavior patch precedence."""

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
    LabelMode,
    NodeBehaviorContext,
    NodeBehaviorPatch,
    OverridePinPolicy,
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


def _context(
    *,
    node_name: str = "node",
    class_type: str = "CustomNode",
    declarative_patch: PackageBehaviorPatch | None = None,
    hook_patch: PackageBehaviorPatch | None = None,
    runtime_patch: NodeBehaviorPatch | None = None,
) -> NodeBehaviorContext:
    """Return a standard resolver context for grouping behavior tests."""

    return NodeBehaviorContext(
        stack_order=("A",),
        cube_alias="A",
        node_name=node_name,
        class_type=class_type,
        node_title=None,
        live_node_definition=None,
        declarative_patch=declarative_patch,
        hook_patch=hook_patch,
        workflow_overrides={},
        node_instance_patch=runtime_patch,
    )


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
        context=_context(node_name="scope", class_type="VectorscopeCC"),
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
        context=_context(
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
        context=_context(declarative_patch=declarative),
    )

    assert resolved.card.enabled_switch_policy == EnabledSwitchPolicy.ALWAYS
    assert resolved.card.enabled_switch_source == ActivationSwitchSource.DECLARATIVE


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
        context=_context(
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


def test_resolver_infers_unqualified_dimension_groups() -> None:
    """Custom nodes with width and height should resolve a dimension group."""

    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("foo", "width", "height", "bar"),
        context=_context(),
    )

    assert resolved.field_groups == (("width", "height"),)


def test_resolver_infers_stemmed_dimension_groups() -> None:
    """Shared dimension stems should resolve independent width/height groups."""

    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=(
            "source_width",
            "source_height",
            "target_width",
            "target_height",
        ),
        context=_context(),
    )

    assert resolved.field_groups == (
        ("source_width", "source_height"),
        ("target_width", "target_height"),
    )


def test_resolver_does_not_infer_mixed_stem_dimension_groups() -> None:
    """Width and height fields with different stems should remain ungrouped."""

    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("source_width", "target_height", "width"),
        context=_context(),
    )

    assert resolved.field_groups == ()


def test_resolver_infers_steps_cfg_common_group_for_arbitrary_class() -> None:
    """Any node with steps and cfg should resolve the common scalar group."""

    resolved = resolve_node_behavior(
        node_name="sampler_like",
        class_type="CustomSampler",
        input_keys=("seed", "steps", "cfg"),
        context=_context(node_name="sampler_like", class_type="CustomSampler"),
    )

    assert resolved.field_groups == (("steps", "cfg"),)


def test_resolver_infers_steps_cfg_common_group_for_detailer() -> None:
    """DetailerForEach should group steps and cfg without a class-specific patch."""

    resolved = resolve_node_behavior(
        node_name="detailer_segs",
        class_type="DetailerForEach",
        input_keys=("guide_size", "steps", "cfg", "denoise"),
        context=_context(node_name="detailer_segs", class_type="DetailerForEach"),
    )

    assert resolved.field_groups == (("steps", "cfg"),)


def test_resolver_does_not_infer_partial_steps_cfg_common_group() -> None:
    """Steps and cfg should not group unless both fields are present."""

    steps_only = resolve_node_behavior(
        node_name="steps_only",
        class_type="CustomSampler",
        input_keys=("seed", "steps"),
        context=_context(node_name="steps_only", class_type="CustomSampler"),
    )
    cfg_only = resolve_node_behavior(
        node_name="cfg_only",
        class_type="CustomSampler",
        input_keys=("seed", "cfg"),
        context=_context(node_name="cfg_only", class_type="CustomSampler"),
    )

    assert steps_only.field_groups == ()
    assert cfg_only.field_groups == ()


def test_resolver_infers_sampler_scheduler_common_group_for_arbitrary_class() -> None:
    """Any node with sampler_name and scheduler should resolve the common group."""

    resolved = resolve_node_behavior(
        node_name="sampler_like",
        class_type="CustomSampler",
        input_keys=("sampler_name", "scheduler", "seed"),
        context=_context(node_name="sampler_like", class_type="CustomSampler"),
    )

    assert resolved.field_groups == (("sampler_name", "scheduler"),)


def test_resolver_authored_groups_override_inferred_common_groups() -> None:
    """Explicit authored groups should remain authoritative over common inference."""

    declarative = PackageBehaviorPatch(
        by_node={
            "node": NodeBehaviorPatch(field_groups=(("steps", "seed"),)),
        }
    )
    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("seed", "sampler_name", "scheduler", "steps", "cfg"),
        context=_context(declarative_patch=declarative),
    )

    assert resolved.field_groups == (("steps", "seed"),)


def test_resolver_appends_dimensions_after_common_groups() -> None:
    """Dimension groups should remain inferred after non-conflicting common groups."""

    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("width", "height", "steps", "cfg"),
        context=_context(),
    )

    assert resolved.field_groups == (("steps", "cfg"), ("width", "height"))


def test_resolver_appends_dimension_groups_after_host_defaults() -> None:
    """Common groups should resolve before non-conflicting dimensions are appended."""

    resolved = resolve_node_behavior(
        node_name="ksampler",
        class_type="KSampler",
        input_keys=("sampler_name", "scheduler", "steps", "cfg", "width", "height"),
        context=_context(node_name="ksampler", class_type="KSampler"),
    )

    assert resolved.field_groups == (
        ("sampler_name", "scheduler"),
        ("steps", "cfg"),
        ("width", "height"),
    )


def test_resolver_marks_steps_and_cfg_as_optional_override_candidates() -> None:
    """Host field defaults should expose steps and cfg without default pinning them."""

    resolved = resolve_node_behavior(
        node_name="ksampler",
        class_type="KSampler",
        input_keys=("seed", "sampler_name", "scheduler", "steps", "cfg"),
        context=_context(node_name="ksampler", class_type="KSampler"),
    )

    expected_policies = {
        "seed": OverridePinPolicy.DEFAULT_PINNED,
        "sampler_name": OverridePinPolicy.DEFAULT_PINNED,
        "scheduler": OverridePinPolicy.DEFAULT_PINNED,
        "steps": OverridePinPolicy.OPTIONAL,
        "cfg": OverridePinPolicy.OPTIONAL,
    }

    for field_key, expected_policy in expected_policies.items():
        override_behavior = resolved.fields[field_key].override_behavior
        assert override_behavior.override_key == field_key
        assert override_behavior.pin_policy == expected_policy


def test_resolver_owns_seedbox_presentation_for_both_comfy_aliases() -> None:
    """Seed aliases should resolve one presentation contract before Qt rendering."""

    resolved = resolve_node_behavior(
        node_name="sampler",
        class_type="SamplerCustom",
        input_keys=("seed", "noise_seed", "ordinary_int"),
        context=_context(node_name="sampler", class_type="SamplerCustom"),
    )

    assert resolved.fields["seed"].presentation is FieldPresentation.SEED_BOX
    assert resolved.fields["noise_seed"].presentation is FieldPresentation.SEED_BOX
    assert resolved.fields["ordinary_int"].presentation is FieldPresentation.STANDARD


def test_resolver_authored_groups_override_inferred_dimension_groups() -> None:
    """Declarative groups should remain authoritative over dimension inference."""

    declarative = PackageBehaviorPatch(
        by_node={
            "node": NodeBehaviorPatch(field_groups=(("width", "steps"),)),
        }
    )
    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("width", "height", "steps"),
        context=_context(declarative_patch=declarative),
    )

    assert resolved.field_groups == (("width", "steps"),)


def test_resolver_empty_authored_groups_opt_out_of_dimension_inference() -> None:
    """An explicit empty group override should suppress inferred dimensions."""

    declarative = PackageBehaviorPatch(
        by_node={"node": NodeBehaviorPatch(field_groups=())}
    )
    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("width", "height"),
        context=_context(declarative_patch=declarative),
    )

    assert resolved.field_groups == ()


def test_resolver_skips_dimensions_that_conflict_with_existing_groups() -> None:
    """Inferred dimensions should not reuse fields already owned by common groups."""

    resolved = resolve_node_behavior(
        node_name="ksampler",
        class_type="KSampler",
        input_keys=("steps", "cfg", "height", "source_width", "source_height"),
        context=_context(node_name="ksampler", class_type="KSampler"),
    )

    assert resolved.field_groups == (
        ("steps", "cfg"),
        ("source_width", "source_height"),
    )
