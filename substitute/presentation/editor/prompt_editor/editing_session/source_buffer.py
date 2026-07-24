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

from dataclasses import dataclass, field

from substitute.application.prompt_editor.editing.literal_parentheses import (
    PromptGeneratedEmphasis,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
    prompt_source_revision,
)

from .parenthesis_intent import PromptParenthesisIntent


@dataclass(frozen=True, slots=True)
class PromptSourceSnapshot:
    """Capture source text with the revision identity that produced it."""

    source_text: str
    source_revision: int
    parenthesis_intents: tuple[PromptParenthesisIntent, ...] = ()
    generated_emphases: tuple[PromptGeneratedEmphasis, ...] = ()
    _identity: PromptSourceIdentity | None = field(
        init=False,
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        """Reject invalid revision identities before they reach session owners."""

        if self.source_revision < 0:
            raise ValueError("Source revision must be non-negative.")

    @property
    def source_length(self) -> int:
        """Return the number of source characters in this snapshot."""

        return len(self.source_text)

    @property
    def identity(self) -> PromptSourceIdentity:
        """Return the typed identity used by commands and derived snapshots."""

        identity = self._identity
        if identity is None:
            identity = PromptSourceIdentity(
                source_revision=prompt_source_revision(self.source_revision),
                source_length=len(self.source_text),
            )
            object.__setattr__(self, "_identity", identity)
        return identity


class PromptSourceBuffer:
    """Own mutable source state and one cached identity per revision."""

    __slots__ = (
        "_generated_emphases",
        "_identity",
        "_parenthesis_intents",
        "_source_revision",
        "_source_text",
    )

    def __init__(
        self,
        source_text: str = "",
        source_revision: int = 0,
        parenthesis_intents: tuple[PromptParenthesisIntent, ...] = (),
        generated_emphases: tuple[PromptGeneratedEmphasis, ...] = (),
    ) -> None:
        """Initialize one validated source revision and its metadata."""

        if source_revision < 0:
            raise ValueError("Source revision must be non-negative.")
        self._source_text = source_text
        self._source_revision = source_revision
        self._parenthesis_intents = parenthesis_intents
        self._generated_emphases = generated_emphases
        self._identity = self._build_identity()

    @property
    def source_text(self) -> str:
        """Return the current source text."""

        return self._source_text

    @property
    def source_revision(self) -> int:
        """Return the current source revision."""

        return self._source_revision

    @property
    def parenthesis_intents(self) -> tuple[PromptParenthesisIntent, ...]:
        """Return source-owned literal-parenthesis intent."""

        return self._parenthesis_intents

    @property
    def generated_emphases(self) -> tuple[PromptGeneratedEmphasis, ...]:
        """Return source-owned generated-emphasis metadata."""

        return self._generated_emphases

    @property
    def source_length(self) -> int:
        """Return the number of source characters currently stored."""

        return len(self._source_text)

    @property
    def identity(self) -> PromptSourceIdentity:
        """Return the typed identity for the current mutable source state."""

        return self._identity

    def replace_state(
        self,
        source_text: str,
        *,
        parenthesis_intents: tuple[PromptParenthesisIntent, ...],
        generated_emphases: tuple[PromptGeneratedEmphasis, ...],
    ) -> None:
        """Replace source-owned state and publish identity only when text changes."""

        source_changed = source_text != self._source_text
        if source_changed:
            self._source_text = source_text
            self._source_revision += 1
            self._identity = self._build_identity()
        self._parenthesis_intents = parenthesis_intents
        self._generated_emphases = generated_emphases

    def snapshot(self) -> PromptSourceSnapshot:
        """Return an immutable view of the current source state."""

        return PromptSourceSnapshot(
            source_text=self._source_text,
            source_revision=self._source_revision,
            parenthesis_intents=self._parenthesis_intents,
            generated_emphases=self._generated_emphases,
        )

    def _build_identity(self) -> PromptSourceIdentity:
        """Build the sole identity allocated for the current source revision."""

        return PromptSourceIdentity(
            source_revision=prompt_source_revision(self._source_revision),
            source_length=len(self._source_text),
        )


__all__ = ["PromptSourceBuffer", "PromptSourceSnapshot"]
