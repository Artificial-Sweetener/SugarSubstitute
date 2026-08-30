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

"""Service-level tests for the prompt editor application layer."""

from __future__ import annotations


from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptAdjustEmphasisAction,
    PromptAdjustLoraWeightAction,
    PromptAdjustWildcardTagAction,
    PromptSetEmphasisWeightAction,
    PromptSetEmphasisWeightContentAction,
    PromptSetLoraWeightAction,
    PromptSetWildcardTagAction,
    PromptConsumeSyntaxAction,
)


def test_prompt_mutation_service_apply_syntax_action_dispatches_emphasis_adjustment() -> (
    None
):
    """Typed syntax actions should reuse the exact-outer-range emphasis mutation path."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "(cat:1.05)",
        PromptAdjustEmphasisAction(
            outer_start=0,
            outer_end=10,
            delta=0.05,
        ),
    )

    assert result is not None
    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("(cat:1.10)", 1, 4, "(cat:1.10)")
    assert result.document_view.emphasis_spans[0].weight_text == "1.10"


def test_prompt_mutation_service_adjustment_crosses_zero_into_negative_weight() -> None:
    """Application-level emphasis actions should retain negative mutation results."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "(cat:0.00)",
        PromptAdjustEmphasisAction(
            outer_start=0,
            outer_end=10,
            delta=-0.05,
        ),
    )

    assert result is not None
    assert result.text == "(cat:-0.05)"
    assert result.document_view.emphasis_spans[0].weight_text == "-0.05"


def test_prompt_mutation_service_apply_syntax_action_dispatches_exact_weight_for_real_shell() -> (
    None
):
    """Typed exact-weight actions should reuse the exact outer-range mutation path."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "(cat:1.05)",
        PromptSetEmphasisWeightAction(
            outer_start=0,
            outer_end=10,
            weight=1.20,
        ),
    )

    assert result is not None
    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("(cat:1.20)", 1, 4, "(cat:1.20)")
    assert result.document_view.emphasis_spans[0].weight_text == "1.20"


def test_prompt_mutation_service_apply_syntax_action_dispatches_exact_weight_for_content_range() -> (
    None
):
    """Typed content-range exact-weight actions should wrap plain text exactly once."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "cat",
        PromptSetEmphasisWeightContentAction(
            content_start=0,
            content_end=3,
            weight=0.95,
        ),
    )

    assert result is not None
    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("(cat:0.95)", 1, 4, "(cat:0.95)")
    assert result.document_view.emphasis_spans[0].weight_text == "0.95"


def test_prompt_mutation_service_apply_syntax_action_exact_neutral_returns_plain_text() -> (
    None
):
    """Exact neutral weight should preserve plain text when no shell exists."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "cat",
        PromptSetEmphasisWeightContentAction(
            content_start=0,
            content_end=3,
            weight=1,
        ),
    )

    assert result is not None
    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("cat", 0, 3, "cat")
    assert result.document_view.emphasis_spans == ()


def test_prompt_mutation_service_apply_syntax_action_returns_none_for_stale_range() -> (
    None
):
    """Typed syntax actions should fail closed when the target outer range is stale."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "(cat:1.05)",
        PromptAdjustEmphasisAction(
            outer_start=0,
            outer_end=9,
            delta=0.05,
        ),
    )

    assert result is None


def test_prompt_mutation_service_apply_syntax_action_consumes_passive_clicks() -> None:
    """Consume-only syntax actions should preserve text while still being routable."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "(cat:1.05)",
        PromptConsumeSyntaxAction(syntax_kind="emphasis"),
    )

    assert result is None


def test_prompt_mutation_service_adjusts_lora_weight_by_outer_range() -> None:
    """LoRA weight mutations should preserve the hidden relative path."""

    mutation_service = PromptMutationService()
    text = r"<lora:Illustrious\Character\Mineru:0.8>"

    result = mutation_service.apply_syntax_action(
        text,
        PromptAdjustLoraWeightAction(
            outer_start=0,
            outer_end=len(text),
            delta=0.1,
        ),
    )

    assert result is not None
    assert result.text == r"<lora:Illustrious\Character\Mineru:0.90>"
    assert result.selection_start == text.index("0.8")
    assert result.selection_end == result.selection_start + len("0.90")


def test_prompt_mutation_service_sets_lora_first_weight_only() -> None:
    """LoRA exact edits should leave the optional second weight unchanged."""

    mutation_service = PromptMutationService()
    text = r"<lora:Mineru:0.8:0.6>"

    result = mutation_service.apply_syntax_action(
        text,
        PromptSetLoraWeightAction(
            outer_start=0,
            outer_end=len(text),
            weight=1.25,
        ),
    )

    assert result is not None
    assert result.text == r"<lora:Mineru:1.25:0.6>"


def test_prompt_mutation_service_allows_negative_lora_weight() -> None:
    """LoRA exact edits should not inherit emphasis minimum clamping."""

    mutation_service = PromptMutationService()
    text = r"<lora:Mineru:0.8:0.6>"

    result = mutation_service.apply_syntax_action(
        text,
        PromptSetLoraWeightAction(
            outer_start=0,
            outer_end=len(text),
            weight=-0.25,
        ),
    )

    assert result is not None
    assert result.text == r"<lora:Mineru:-0.25:0.6>"


def test_prompt_mutation_service_sets_implicit_wildcard_tag_explicitly() -> None:
    """Editing an implicit wildcard group should persist an explicit tag suffix."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "{monster}, {monster}",
        PromptAdjustWildcardTagAction(
            outer_start=11,
            outer_end=20,
            current_display_tag="1",
            delta=1,
        ),
    )

    assert result is not None
    assert result.text == "{monster}, {monster|2}"
    assert result.selection_start == len("{monster}, {monster|2}") - 1
    assert result.selection_end == result.selection_start


def test_prompt_mutation_service_increments_explicit_wildcard_numeric_tag() -> None:
    """Explicit positive integer wildcard tags should step upward."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "{monster|1}",
        PromptAdjustWildcardTagAction(
            outer_start=0,
            outer_end=11,
            current_display_tag="1",
            delta=1,
        ),
    )

    assert result is not None
    assert result.text == "{monster|2}"


def test_prompt_mutation_service_decrements_explicit_wildcard_numeric_tag() -> None:
    """Explicit positive integer wildcard tags should step downward to one."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "{monster|2}",
        PromptAdjustWildcardTagAction(
            outer_start=0,
            outer_end=11,
            current_display_tag="2",
            delta=-1,
        ),
    )

    assert result is not None
    assert result.text == "{monster|1}"


def test_prompt_mutation_service_does_not_adjust_nonnumeric_wildcard_tag() -> None:
    """Nonnumeric wildcard tags should be display-only for numeric stepping."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "{monster|one}",
        PromptAdjustWildcardTagAction(
            outer_start=0,
            outer_end=13,
            current_display_tag="one",
            delta=1,
        ),
    )

    assert result is None


def test_prompt_mutation_service_sets_csv_wildcard_tag_without_rewriting_body() -> None:
    """CSV wildcard tag edits should preserve the identifier and selected column."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "{csv:monster:color}",
        PromptSetWildcardTagAction(
            outer_start=0,
            outer_end=19,
            tag="2",
        ),
    )

    assert result is not None
    assert result.text == "{csv:monster:color|2}"
