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

"""Aggregate one immutable prompt projection document and transient adornments."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

from substitute.application.prompt_editor.document.views import (
    PromptRegionStructureView,
)

from .caret import PromptProjectionCaretMap
from .mapping import PromptProjectionMapping
from .runs import PromptProjectionRun
from .tokens import PromptProjectionToken


class PromptProjectionDisplayMode(str, Enum):
    """Enumerate the supported prompt editor display modes."""

    RAW = "raw"
    PROJECTED = "projected"


@dataclass(frozen=True, slots=True)
class PromptProjectionDocument:
    """Describe one full run-based prompt projection plus its lookup mapping."""

    display_mode: PromptProjectionDisplayMode
    source_text: str
    projection_text: str
    runs: Sequence[PromptProjectionRun]
    tokens: Sequence[PromptProjectionToken]
    mapping: PromptProjectionMapping
    caret_map: PromptProjectionCaretMap
    region_structure: PromptRegionStructureView
    _tokens_by_id: dict[str, PromptProjectionToken] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )

    @classmethod
    def empty(cls) -> PromptProjectionDocument:
        """Return the valid raw projection used before source publication."""

        return cls(
            display_mode=PromptProjectionDisplayMode.RAW,
            source_text="",
            projection_text="",
            runs=(),
            tokens=(),
            mapping=PromptProjectionMapping((), 0, 0),
            caret_map=PromptProjectionCaretMap(
                stops=(),
                tokens=(),
                source_length=0,
                projection_length=0,
            ),
            region_structure=PromptRegionStructureView.empty(0),
        )

    def token_by_id(self, token_id: str | None) -> PromptProjectionToken | None:
        """Return the semantic token matching one stable token identifier."""

        if token_id is None:
            return None
        optimized_lookup = getattr(self.tokens, "token_by_id", None)
        if callable(optimized_lookup):
            token = optimized_lookup(token_id)
            return token if isinstance(token, PromptProjectionToken) else None
        tokens_by_id = self._tokens_by_id
        if tokens_by_id is None:
            tokens_by_id = {token.token_id: token for token in self.tokens}
            object.__setattr__(self, "_tokens_by_id", tokens_by_id)
        return tokens_by_id.get(token_id)

    def run_by_id(self, run_id: str | None) -> PromptProjectionRun | None:
        """Return the visible run matching one stable run identifier."""

        return self.mapping.run_by_id(run_id)

    def runs_for_token(
        self,
        token_id: str,
    ) -> tuple[PromptProjectionRun, ...]:
        """Return the visible runs owned by one semantic token."""

        return self.mapping.runs_for_token(token_id)


@dataclass(frozen=True, slots=True)
class PromptProjectionInlinePreview:
    """Describe visible inline projection text that is not committed source."""

    source_position: int
    suffix_text: str


@dataclass(frozen=True, slots=True)
class PromptProjectionTransientState:
    """Collect transient projection adornments applied to the active document."""

    autocomplete_preview: PromptProjectionInlinePreview | None = None
