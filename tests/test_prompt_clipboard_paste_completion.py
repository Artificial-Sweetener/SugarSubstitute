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

"""Verify clipboard completion has one post-construction refresh owner."""

from __future__ import annotations

from typing import cast

import pytest

from substitute.presentation.editor.prompt_editor.interactions.clipboard_paste_completion import (
    PromptClipboardPasteCompletionOwner,
)
from substitute.presentation.editor.prompt_editor.interactions.controller import (
    PromptInteractionController,
)


class _InteractionDouble:
    """Record semantic refresh commands issued by clipboard completion."""

    def __init__(self) -> None:
        """Initialize the recorded refresh reasons."""

        self.reasons: list[str] = []

    def flush_pending_semantic_refresh(self, *, reason: str) -> None:
        """Record one semantic-refresh command."""

        self.reasons.append(reason)


def test_clipboard_paste_completion_is_inert_until_interaction_is_bound() -> None:
    """Avoid refresh work while projection collaborators are still constructing."""

    owner = PromptClipboardPasteCompletionOwner()

    owner.complete("paste")


def test_clipboard_paste_completion_flushes_the_bound_interaction() -> None:
    """Route each accepted paste completion to the one interaction authority."""

    owner = PromptClipboardPasteCompletionOwner()
    interaction = _InteractionDouble()
    owner.bind_interaction(cast(PromptInteractionController, interaction))

    owner.complete("drop_plain_text")

    assert interaction.reasons == ["drop_plain_text"]


def test_clipboard_paste_completion_rejects_rebinding() -> None:
    """Keep semantic-refresh ownership single-writer after construction."""

    owner = PromptClipboardPasteCompletionOwner()
    owner.bind_interaction(cast(PromptInteractionController, _InteractionDouble()))

    with pytest.raises(RuntimeError, match="already bound"):
        owner.bind_interaction(cast(PromptInteractionController, _InteractionDouble()))
