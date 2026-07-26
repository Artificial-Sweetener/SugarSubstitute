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

"""Define immutable visible runs emitted by prompt projection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

OBJECT_REPLACEMENT_CHARACTER = "\ufffc"


class PromptProjectionRunKind(str, Enum):
    """Enumerate the visible run kinds emitted by the projection builder."""

    TEXT = "text"
    INLINE_OBJECT = "inline_object"
    STRUCTURAL_ROW = "structural_row"


class PromptProjectionRunRole(str, Enum):
    """Enumerate special token-decoration roles assigned to projection runs."""

    DEFAULT = "default"
    TOKEN_LEADING_DECORATION = "token_leading_decoration"
    TOKEN_TRAILING_DECORATION = "token_trailing_decoration"


@dataclass(frozen=True, slots=True)
class PromptProjectionRun:
    """Describe one visible inline run emitted by the projection builder."""

    run_id: str
    kind: PromptProjectionRunKind
    source_start: int
    source_end: int
    display_text: str
    source_positions: Sequence[int]
    projection_start: int
    projection_end: int
    token_id: str | None = None
    renderer_key: str | None = None
    role: PromptProjectionRunRole = PromptProjectionRunRole.DEFAULT
    active: bool = False
    source_backed: bool = True
    ghosted: bool = False
    text_style_variant: str | None = None

    def __post_init__(self) -> None:
        """Validate the run invariants required by the unified layout path."""

        if self.kind is PromptProjectionRunKind.TEXT:
            expected_boundary_count = len(self.display_text) + 1
            if len(self.source_positions) != expected_boundary_count:
                raise ValueError(
                    "Text runs must expose one source boundary for each visible "
                    f"character plus one trailing boundary. Got "
                    f"{len(self.source_positions)} boundaries for "
                    f"{len(self.display_text)} visible characters."
                )
            if self.projection_end - self.projection_start != len(self.display_text):
                raise ValueError(
                    "Text run projection ranges must match the visible text length."
                )
        elif self.kind is PromptProjectionRunKind.INLINE_OBJECT:
            if len(self.source_positions) < 2:
                raise ValueError(
                    "Inline object runs must expose at least leading and trailing "
                    "source boundaries."
                )
            if self.projection_end - self.projection_start != 1:
                raise ValueError(
                    "Inline object runs must occupy exactly one projection slot."
                )
            if self.renderer_key is None:
                raise ValueError(
                    "Inline object runs must declare the renderer key that owns them."
                )
        else:
            if self.projection_end - self.projection_start != 1:
                raise ValueError("Structural rows must occupy one projection slot.")
            if self.token_id is None:
                raise ValueError("Structural rows must reference their source token.")
            if self.renderer_key is not None:
                raise ValueError("Structural rows cannot use inline-object renderers.")

    @property
    def is_text(self) -> bool:
        """Return whether this run contributes visible text characters."""

        return self.kind is PromptProjectionRunKind.TEXT

    @property
    def is_inline_object(self) -> bool:
        """Return whether this run contributes one inline object slot."""

        return self.kind is PromptProjectionRunKind.INLINE_OBJECT

    @property
    def is_structural_row(self) -> bool:
        """Return whether this run contributes layout structure without content."""

        return self.kind is PromptProjectionRunKind.STRUCTURAL_ROW
