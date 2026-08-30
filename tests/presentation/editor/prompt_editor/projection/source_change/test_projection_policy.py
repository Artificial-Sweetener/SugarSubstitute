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

"""Verify source-edit projection deferral policy."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.source_edit_projection_policy import (
    PromptSourceEditProjectionDecision,
    PromptSourceEditProjectionPolicy,
)
from substitute.presentation.editor.prompt_editor.projection.source_edit_syntax import (
    is_deferred_syntax_autocomplete_prefix,
)


@pytest.mark.parametrize(
    ("replacement_text", "reason"),
    (
        ("", "deletion_requires_immediate_projection"),
        (" ", "whitespace_requires_immediate_projection"),
        ("\n", "whitespace_requires_immediate_projection"),
    ),
)
def test_source_edit_projection_policy_forces_immediate_boundaries(
    replacement_text: str,
    reason: str,
) -> None:
    """Deletion and whitespace edits are immediate projection boundaries."""

    decision = PromptSourceEditProjectionPolicy().decide(
        can_defer_projection=True,
        deferral_reason="safe_typing",
        replacement_text=replacement_text,
        autocomplete_preview_active=False,
        insertion_overlay_can_defer=True,
    )

    assert not decision.can_defer_projection
    assert decision.deferral_reason == reason


def test_source_edit_projection_policy_forces_preview_active_edits_immediate() -> None:
    """Edits cannot defer while autocomplete preview is active."""

    decision = PromptSourceEditProjectionPolicy().decide(
        can_defer_projection=True,
        deferral_reason="safe_typing",
        replacement_text="x",
        autocomplete_preview_active=True,
        insertion_overlay_can_defer=True,
    )

    assert not decision.can_defer_projection
    assert decision.deferral_reason == "autocomplete_preview_active"


def test_source_edit_projection_policy_rejects_missing_insertion_overlay() -> None:
    """Text insertions that cannot paint as overlays require full layout."""

    decision = PromptSourceEditProjectionPolicy().decide(
        can_defer_projection=True,
        deferral_reason="safe_typing",
        replacement_text="x",
        autocomplete_preview_active=False,
        insertion_overlay_can_defer=False,
    )

    assert not decision.can_defer_projection
    assert decision.deferral_reason == "safe_typing_requires_layout"


def test_source_edit_projection_policy_allows_safe_plain_insert() -> None:
    """Plain non-whitespace insertions can defer when overlays can represent them."""

    decision = PromptSourceEditProjectionPolicy().decide(
        can_defer_projection=True,
        deferral_reason="safe_typing",
        replacement_text="x",
        autocomplete_preview_active=False,
        insertion_overlay_can_defer=True,
    )

    assert decision.can_defer_projection
    assert decision.deferral_reason == "safe_typing"


@pytest.mark.parametrize(
    "reason",
    (
        "plain_single_character",
        "plain_single_character_requires_layout",
        "plain_single_character_delete",
        "plain_single_character_delete_requires_layout",
        "syntax_sensitive_autocomplete_prefix",
    ),
)
def test_source_edit_projection_decision_allows_safe_wrap_recovery(
    reason: str,
) -> None:
    """Plain edit decisions retain stale-safe recovery at wrap boundaries."""

    decision = PromptSourceEditProjectionDecision(
        can_defer_projection=False,
        deferral_reason=reason,
    )

    assert decision.wrap_reflow_deferrable


@pytest.mark.parametrize(
    ("character", "comma_requires_projection", "expected"),
    (
        ("x", False, False),
        ("(", False, True),
        ("*", False, True),
        (",", False, False),
        (",", True, True),
    ),
)
def test_source_edit_projection_policy_classifies_syntax_characters(
    character: str,
    comma_requires_projection: bool,
    expected: bool,
) -> None:
    """Syntax and context-sensitive comma edits have one policy owner."""

    assert (
        PromptSourceEditProjectionPolicy().typed_character_requires_projection(
            character,
            comma_requires_projection=comma_requires_projection,
        )
        is expected
    )


@pytest.mark.parametrize(
    ("text", "position", "focused_range", "expected"),
    (
        ("<", 0, None, True),
        ("<lora:", len("<lora"), None, True),
        ("prefix <lora:", len("prefix <lora"), None, False),
        ("<lora:name>", len("<lora:name"), None, False),
        ("alpha, <", len("alpha, "), (0, len("alpha")), True),
        ("alpha, <", len("alpha, "), (6, len("alpha, ") + 1), False),
    ),
)
def test_source_edit_projection_policy_classifies_autocomplete_prefix(
    text: str,
    position: int,
    focused_range: tuple[int, int] | None,
    expected: bool,
) -> None:
    """Only incomplete LoRA prefixes outside token interiors may defer."""

    assert (
        is_deferred_syntax_autocomplete_prefix(
            start=position,
            end=position,
            replacement_text=text[position],
            normalized_text=text,
            focused_token_range=focused_range,
        )
        is expected
    )


def test_source_edit_projection_policy_queries_token_boundaries() -> None:
    """Token intersection and interior checks share the projection policy owner."""

    token = PromptProjectionToken(
        token_id="token",
        kind=PromptProjectionTokenKind.LORA,
        source_start=4,
        source_end=12,
        display_text="lora",
    )
    policy = PromptSourceEditProjectionPolicy()

    assert policy.source_range_intersects_tokens(start=3, end=5, tokens=(token,))
    assert not policy.source_range_intersects_tokens(start=0, end=4, tokens=(token,))
    assert policy.source_insertion_is_inside_token(
        source_position=8,
        tokens=(token,),
    )
    assert not policy.source_insertion_is_inside_token(
        source_position=4,
        tokens=(token,),
    )
