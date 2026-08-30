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

"""Provide immutable inputs shared by revision-state owner tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorState,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    """Provide immutable source input for focused state-owner tests."""

    source_text: str
    source_revision: int
    _identity: PromptSourceIdentity = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Cache the identity owned by this immutable source."""

        object.__setattr__(
            self,
            "_identity",
            PromptSourceIdentity(self.source_revision, len(self.source_text)),
        )

    @property
    def identity(self) -> PromptSourceIdentity:
        """Return the source-owned identity."""

        return self._identity

    @property
    def source_length(self) -> int:
        """Return the source length."""

        return len(self.source_text)


@dataclass(frozen=True, slots=True)
class SourceValue:
    """Provide a source-derived semantic or projection value."""

    source_text: str
    marker: str


def state() -> PromptEditorState[SourceValue, str, SourceValue, str, str]:
    """Return a revision owner with one valid initial chain."""

    return PromptEditorState(
        source=SourceSnapshot("alpha", 0),
        semantic_document=SourceValue("alpha", "semantic-0"),
        render_plan="render-0",
        projection_document=SourceValue("alpha", "projection-0"),
    )
