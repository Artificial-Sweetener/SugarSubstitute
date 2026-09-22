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

"""Verify lazy token-coordinate remapping across plain-text edits."""

from __future__ import annotations

from collections.abc import Sequence
from typing import overload

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.incremental_edit_contracts import (
    PromptProjectionIncrementalEdit,
)
from substitute.presentation.editor.prompt_editor.projection.plain_edit_token_sequence import (
    PromptProjectionPlainEditTokenSequence,
)


class _CountingTokenSequence(Sequence[PromptProjectionToken]):
    """Expose immutable tokens while recording materialized entries."""

    def __init__(self, tokens: tuple[PromptProjectionToken, ...]) -> None:
        """Store tokens and initialize indexed-read tracking."""

        self._tokens = tokens
        self.read_count = 0

    def __len__(self) -> int:
        """Return the token count."""

        return len(self._tokens)

    @overload
    def __getitem__(self, index: int) -> PromptProjectionToken: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[PromptProjectionToken, ...]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> PromptProjectionToken | tuple[PromptProjectionToken, ...]:
        """Return requested tokens while counting integer reads."""

        if isinstance(index, slice):
            return self._tokens[index]
        self.read_count += 1
        return self._tokens[index]


def _token(token_id: str, start: int, end: int) -> PromptProjectionToken:
    """Return one token with content coordinates inside its source range."""

    return PromptProjectionToken(
        token_id=token_id,
        kind=PromptProjectionTokenKind.EMPHASIS,
        source_start=start,
        source_end=end,
        content_start=start + 1,
        content_end=end - 1,
        display_text=token_id,
    )


def _insert(
    *, position: int, text: str, previous: str
) -> PromptProjectionIncrementalEdit:
    """Return one insertion edit against the supplied previous source."""

    return PromptProjectionIncrementalEdit(
        start=position,
        end=position,
        replacement_text=text,
        previous_source_text=previous,
        next_source_text=previous[:position] + text + previous[position:],
    )


def _delete(*, start: int, end: int, previous: str) -> PromptProjectionIncrementalEdit:
    """Return one deletion edit against the supplied previous source."""

    return PromptProjectionIncrementalEdit(
        start=start,
        end=end,
        replacement_text="",
        previous_source_text=previous,
        next_source_text=previous[:start] + previous[end:],
    )


def test_token_sequence_defers_coordinate_materialization_until_lookup() -> None:
    """Construction and identifier snapshots must not shift token objects."""

    base = _CountingTokenSequence((_token("before", 0, 2), _token("after", 5, 10)))
    tokens = PromptProjectionPlainEditTokenSequence(
        base,
        edit=_insert(position=3, text="++", previous="ab cd token"),
    )

    assert base.read_count == 0
    assert tokens.token_ids() == frozenset({"before", "after"})
    assert base.read_count == 2

    shifted = tokens.token_by_id("after")

    assert shifted is not None
    assert (shifted.source_start, shifted.source_end) == (7, 12)
    assert (shifted.content_start, shifted.content_end) == (8, 11)
    assert tokens.token_by_id("after") is shifted
    assert base.read_count == 3


def test_token_sequence_flattens_consecutive_edits_onto_original_tokens() -> None:
    """Repeated plain edits allocate one final shifted token on demand."""

    original = _token("token", 5, 10)
    first = PromptProjectionPlainEditTokenSequence(
        (original,),
        edit=_insert(position=2, text="++", previous="ab token"),
    )
    second = PromptProjectionPlainEditTokenSequence(
        first,
        edit=_insert(position=4, text="z", previous="ab++ token"),
    )

    shifted = second[0]

    assert (shifted.source_start, shifted.source_end) == (8, 13)
    assert (shifted.content_start, shifted.content_end) == (9, 12)
    assert second[0] is shifted


def test_token_sequence_preserves_token_ending_at_insert_boundary() -> None:
    """Insertion after a token must not make that token consume plain text."""

    original = _token("token", 2, 7)
    tokens = PromptProjectionPlainEditTokenSequence(
        (original,),
        edit=_insert(position=7, text="x", previous="__token"),
    )

    assert tokens[0] is original


def test_token_sequence_shifts_only_tokens_after_plain_deletion() -> None:
    """Deletion remaps later tokens while retaining earlier token identity."""

    before = _token("before", 0, 2)
    after = _token("after", 5, 10)
    tokens = PromptProjectionPlainEditTokenSequence(
        (before, after),
        edit=_delete(start=2, end=4, previous="abXX token"),
    )

    assert tokens[0] is before
    assert (tokens[1].source_start, tokens[1].source_end) == (3, 8)
    assert (tokens[1].content_start, tokens[1].content_end) == (4, 7)


def test_token_sequence_compares_by_contents_and_supports_sequence_access() -> None:
    """Lazy storage must retain the projection document's sequence contract."""

    original = _token("token", 2, 7)
    tokens = PromptProjectionPlainEditTokenSequence(
        (original,),
        edit=_insert(position=7, text="x", previous="__token"),
    )
    empty = PromptProjectionPlainEditTokenSequence(
        (),
        edit=_insert(position=0, text="x", previous=""),
    )

    assert tokens == (original,)
    assert tokens[-1] is original
    assert tokens[:] == (original,)
    assert empty == ()
