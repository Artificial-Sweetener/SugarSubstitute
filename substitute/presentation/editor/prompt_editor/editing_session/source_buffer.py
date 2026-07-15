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

"""Define source text state primitives for the prompt editing session."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.prompt_literal_parenthesis_normalizer import (
    PromptGeneratedEmphasis,
)

from .parenthesis_intent import PromptParenthesisIntent


@dataclass(frozen=True, slots=True)
class PromptSourceSnapshot:
    """Capture source text with the revision identity that produced it."""

    source_text: str
    source_revision: int
    parenthesis_intents: tuple[PromptParenthesisIntent, ...] = ()
    generated_emphases: tuple[PromptGeneratedEmphasis, ...] = ()

    def __post_init__(self) -> None:
        """Reject invalid revision identities before they reach session owners."""

        if self.source_revision < 0:
            raise ValueError("Source revision must be non-negative.")

    @property
    def source_length(self) -> int:
        """Return the number of source characters in this snapshot."""

        return len(self.source_text)


@dataclass(slots=True)
class PromptSourceBuffer:
    """Store prompt source text and revision without owning edit behavior yet."""

    source_text: str = ""
    source_revision: int = 0
    parenthesis_intents: tuple[PromptParenthesisIntent, ...] = ()
    generated_emphases: tuple[PromptGeneratedEmphasis, ...] = ()

    def __post_init__(self) -> None:
        """Reject invalid revision identities before mutation behavior is added."""

        if self.source_revision < 0:
            raise ValueError("Source revision must be non-negative.")

    @property
    def source_length(self) -> int:
        """Return the number of source characters currently stored."""

        return len(self.source_text)

    def snapshot(self) -> PromptSourceSnapshot:
        """Return an immutable view of the current source state."""

        return PromptSourceSnapshot(
            source_text=self.source_text,
            source_revision=self.source_revision,
            parenthesis_intents=self.parenthesis_intents,
            generated_emphases=self.generated_emphases,
        )


__all__ = ["PromptSourceBuffer", "PromptSourceSnapshot"]
