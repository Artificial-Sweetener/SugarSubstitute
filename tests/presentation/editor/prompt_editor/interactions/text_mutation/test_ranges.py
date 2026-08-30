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

"""Verify authoritative source ranges for projected text mutations."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
)
from substitute.presentation.editor.prompt_editor.interactions.text_mutation_controller import (
    PromptProjectionTextMutationContext,
    PromptProjectionTextMutationRangeResolver,
    PromptProjectionTextMutationRequest,
)


def _token(
    kind: PromptProjectionTokenKind,
    *,
    navigation_mode: PromptProjectionTokenNavigationMode,
) -> PromptProjectionToken:
    """Return one token with distinct outer and content boundaries."""

    return PromptProjectionToken(
        token_id=kind.value,
        kind=kind,
        source_start=2,
        source_end=12,
        display_text="content",
        value_text="value",
        content_start=3,
        content_end=10,
        navigation_mode=navigation_mode,
    )


def _context(
    token: PromptProjectionToken,
    *,
    position: int,
    placement: PromptProjectionCaretPlacement,
    anchor_position: int | None = None,
) -> PromptProjectionTextMutationContext:
    """Return mutation context focused on one token-backed caret state."""

    anchor = position if anchor_position is None else anchor_position
    cursor_state = PromptProjectionCaretState(
        source_position=position,
        placement=placement,
        token_id=token.token_id,
    )
    anchor_state = PromptProjectionCaretState(
        source_position=anchor,
        placement=placement,
        token_id=token.token_id,
    )
    return PromptProjectionTextMutationContext(
        selection=PromptProjectionSelection(
            anchor_position=anchor,
            cursor_position=position,
        ),
        cursor_state=cursor_state,
        anchor_state=anchor_state,
        tokens=(token,),
        editing_enabled=True,
    )


@pytest.mark.parametrize("kind", tuple(PromptProjectionTokenKind))
def test_each_token_kind_resolves_its_legitimate_outer_boundaries(
    kind: PromptProjectionTokenKind,
) -> None:
    """Keep atomic and text-content decorations on their visible outer edges."""

    navigation_mode = (
        PromptProjectionTokenNavigationMode.TEXT_CONTENT
        if kind in {PromptProjectionTokenKind.EMPHASIS, PromptProjectionTokenKind.SCENE}
        else PromptProjectionTokenNavigationMode.ATOMIC
    )
    token = _token(kind, navigation_mode=navigation_mode)
    resolver = PromptProjectionTextMutationRangeResolver()

    leading = resolver.resolve(
        _context(
            token,
            position=token.source_start,
            placement=PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE,
        ),
        PromptProjectionTextMutationRequest(
            token.source_start,
            token.source_start,
            " ",
        ),
    )
    trailing = resolver.resolve(
        _context(
            token,
            position=token.source_end,
            placement=PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
        ),
        PromptProjectionTextMutationRequest(
            token.source_end,
            token.source_end,
            " ",
        ),
    )

    assert (leading.start, leading.end) == (token.source_start, token.source_start)
    assert (trailing.start, trailing.end) == (token.source_end, token.source_end)


@pytest.mark.parametrize(
    "kind",
    (PromptProjectionTokenKind.EMPHASIS, PromptProjectionTokenKind.SCENE),
)
def test_space_at_text_content_end_preserves_requested_source_boundary(
    kind: PromptProjectionTokenKind,
) -> None:
    """Keep direct text inside text-content tokens despite hidden suffixes."""

    token = _token(
        kind,
        navigation_mode=PromptProjectionTokenNavigationMode.TEXT_CONTENT,
    )
    resolver = PromptProjectionTextMutationRangeResolver()
    assert token.content_end is not None
    resolved = resolver.resolve(
        _context(
            token,
            position=token.content_end,
            placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
        ),
        PromptProjectionTextMutationRequest(
            token.content_end,
            token.content_end,
            " ",
        ),
    )

    assert (resolved.start, resolved.end) == (token.content_end, token.content_end)


@pytest.mark.parametrize(
    ("placement", "expected_position"),
    (
        (PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE, 2),
        (PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE, 12),
    ),
)
def test_atomic_hidden_positions_resolve_to_the_visible_caret_edge(
    placement: PromptProjectionCaretPlacement,
    expected_position: int,
) -> None:
    """Prevent raw positions inside atomic syntax from becoming edit targets."""

    token = _token(
        PromptProjectionTokenKind.WILDCARD,
        navigation_mode=PromptProjectionTokenNavigationMode.ATOMIC,
    )
    context = _context(token, position=6, placement=placement)
    resolved = PromptProjectionTextMutationRangeResolver().resolve(
        context,
        PromptProjectionTextMutationRequest(6, 6, " "),
    )

    assert (resolved.start, resolved.end) == (expected_position, expected_position)


def test_syntax_replacement_of_emphasis_content_targets_the_outer_token() -> None:
    """Preserve the existing wrapper replacement contract after extraction."""

    token = _token(
        PromptProjectionTokenKind.EMPHASIS,
        navigation_mode=PromptProjectionTokenNavigationMode.TEXT_CONTENT,
    )
    assert token.content_start is not None
    assert token.content_end is not None
    context = _context(
        token,
        position=token.content_end,
        anchor_position=token.content_start,
        placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
    )
    resolved = PromptProjectionTextMutationRangeResolver().resolve(
        context,
        PromptProjectionTextMutationRequest(
            token.content_start,
            token.content_end,
            "(replacement)",
        ),
    )

    assert (resolved.start, resolved.end) == (token.source_start, token.source_end)


def test_explicit_relative_replacement_is_not_reinterpreted_as_caret_insertion() -> (
    None
):
    """Preserve IME replacement ranges that intentionally differ from selection."""

    token = _token(
        PromptProjectionTokenKind.EMPHASIS,
        navigation_mode=PromptProjectionTokenNavigationMode.TEXT_CONTENT,
    )
    assert token.content_end is not None
    context = _context(
        token,
        position=token.content_end,
        placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
    )
    resolved = PromptProjectionTextMutationRangeResolver().resolve(
        context,
        PromptProjectionTextMutationRequest(4, 6, "字"),
    )

    assert (resolved.start, resolved.end) == (4, 6)
