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

"""Expose lazily shifted semantic tokens across plain-text edits."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import replace
from typing import overload

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)

from .incremental_edit_contracts import PromptProjectionIncrementalEdit
from .plain_edit_coordinates import (
    PromptSourceEditCoordinates,
    remap_optional_source_position,
    remap_source_position,
)


class PromptProjectionPlainEditTokenSequence(Sequence[PromptProjectionToken]):
    """Shift token coordinates lazily while preserving stable token identities."""

    __slots__ = (
        "_base_tokens",
        "_cache",
        "_edits",
        "_index_by_id",
        "_token_ids",
    )
    _base_tokens: Sequence[PromptProjectionToken]
    _cache: dict[int, PromptProjectionToken]
    _edits: tuple[PromptSourceEditCoordinates, ...]
    _index_by_id: dict[str, int] | None
    _token_ids: frozenset[str] | None

    def __init__(
        self,
        base_tokens: Sequence[PromptProjectionToken],
        *,
        edit: PromptProjectionIncrementalEdit,
        edited_token: PromptProjectionToken | None = None,
    ) -> None:
        """Flatten consecutive edits onto one immutable token sequence."""

        coordinate_edit = PromptSourceEditCoordinates.from_incremental_edit(edit)
        if isinstance(base_tokens, PromptProjectionPlainEditTokenSequence):
            self._base_tokens = base_tokens._base_tokens
            self._edits = base_tokens._edits + (coordinate_edit,)
            self._token_ids = base_tokens._token_ids
        else:
            self._base_tokens = base_tokens
            self._edits = (coordinate_edit,)
            self._token_ids = None
        self._cache: dict[int, PromptProjectionToken] = {}
        self._index_by_id: dict[str, int] | None = (
            base_tokens._index_by_id
            if isinstance(base_tokens, PromptProjectionPlainEditTokenSequence)
            else None
        )
        if edited_token is not None:
            self._ensure_identifier_index()
            assert self._index_by_id is not None
            edited_index = self._index_by_id.get(edited_token.token_id)
            if edited_index is None:
                raise ValueError("Edited token is absent from the base sequence.")
            self._cache[edited_index] = edited_token

    def __len__(self) -> int:
        """Return the stable token count."""

        return len(self._base_tokens)

    @overload
    def __getitem__(self, index: int) -> PromptProjectionToken: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[PromptProjectionToken, ...]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> PromptProjectionToken | tuple[PromptProjectionToken, ...]:
        """Return one shifted token or a materialized slice."""

        if isinstance(index, slice):
            return tuple(
                self[position] for position in range(*index.indices(len(self)))
            )
        normalized_index = index + len(self) if index < 0 else index
        if normalized_index < 0 or normalized_index >= len(self):
            raise IndexError(index)
        return self._token_at(normalized_index)

    def __iter__(self) -> Iterator[PromptProjectionToken]:
        """Yield tokens while materializing each shifted value at most once."""

        for index in range(len(self._base_tokens)):
            yield self._token_at(index)

    def __eq__(self, other: object) -> bool:
        """Compare token contents when callers explicitly request equality."""

        if not isinstance(other, Sequence):
            return False
        return tuple(self) == tuple(other)

    def token_by_id(self, token_id: str) -> PromptProjectionToken | None:
        """Return one token by stable identifier without shifting its peers."""

        self._ensure_identifier_index()
        assert self._index_by_id is not None
        index = self._index_by_id.get(token_id)
        return None if index is None else self._token_at(index)

    def token_ids(self) -> frozenset[str]:
        """Return stable token identifiers without shifting token coordinates."""

        token_ids = self._token_ids
        if token_ids is None:
            self._ensure_identifier_index()
            assert self._token_ids is not None
            token_ids = self._token_ids
        return token_ids

    def _ensure_identifier_index(self) -> None:
        """Build stable token identifiers once without shifting coordinates."""

        if self._index_by_id is not None:
            return
        index_by_id = {
            self._base_tokens[index].token_id: index
            for index in range(len(self._base_tokens))
        }
        self._index_by_id = index_by_id
        self._token_ids = frozenset(index_by_id)

    def _token_at(self, index: int) -> PromptProjectionToken:
        """Return one cached token with every pending coordinate edit applied."""

        cached = self._cache.get(index)
        if cached is not None:
            return cached
        token = _apply_coordinate_edits(self._base_tokens[index], self._edits)
        self._cache[index] = token
        return token


def _apply_coordinate_edits(
    token: PromptProjectionToken,
    edits: tuple[PromptSourceEditCoordinates, ...],
) -> PromptProjectionToken:
    """Apply ordered non-token edits and allocate at most one shifted token."""

    source_start = token.source_start
    source_end = token.source_end
    content_start = token.content_start
    content_end = token.content_end
    for edit in edits:
        if source_end < edit.start:
            continue
        if (
            edit.start == edit.end
            and source_start < edit.start
            and source_end == edit.start
        ):
            continue
        source_start = remap_source_position(
            source_start,
            edit_start=edit.start,
            edit_end=edit.end,
            delta=edit.delta,
            move_insert_boundary=True,
        )
        source_end = remap_source_position(
            source_end,
            edit_start=edit.start,
            edit_end=edit.end,
            delta=edit.delta,
            move_insert_boundary=True,
        )
        content_start = remap_optional_source_position(
            content_start,
            edit_start=edit.start,
            edit_end=edit.end,
            delta=edit.delta,
            move_insert_boundary=True,
        )
        content_end = remap_optional_source_position(
            content_end,
            edit_start=edit.start,
            edit_end=edit.end,
            delta=edit.delta,
            move_insert_boundary=True,
        )
    if (
        source_start == token.source_start
        and source_end == token.source_end
        and content_start == token.content_start
        and content_end == token.content_end
    ):
        return token
    return replace(
        token,
        source_start=source_start,
        source_end=source_end,
        content_start=content_start,
        content_end=content_end,
    )


__all__ = ["PromptProjectionPlainEditTokenSequence"]
