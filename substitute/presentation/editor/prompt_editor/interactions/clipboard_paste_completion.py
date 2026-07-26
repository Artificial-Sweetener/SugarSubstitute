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

"""Publish semantic refresh completion after clipboard-originated edits."""

from __future__ import annotations

from .controller import PromptInteractionController


class PromptClipboardPasteCompletionOwner:
    """Own the post-paste handoff from editing runtime to interaction refresh."""

    def __init__(self) -> None:
        """Start unbound while projection collaborators are being constructed."""

        self._interaction: PromptInteractionController | None = None

    def bind_interaction(self, interaction: PromptInteractionController) -> None:
        """Bind the sole semantic-refresh command consumer after construction."""

        if self._interaction is not None:
            raise RuntimeError(
                "Clipboard paste completion interaction is already bound."
            )
        self._interaction = interaction

    def complete(self, reason: str) -> None:
        """Flush the current semantic refresh after one accepted paste command."""

        interaction = self._interaction
        if interaction is not None:
            interaction.flush_pending_semantic_refresh(reason=reason)
