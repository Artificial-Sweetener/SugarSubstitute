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

"""Bridge scheduled-LoRA context across autocomplete construction phases."""

from __future__ import annotations

from collections.abc import Hashable

from ..core.state.revisions import PromptSourceIdentity
from ..features import PromptAutocompleteScheduledLoraCurrentContext


class PromptAutocompleteCurrentContextBridge:
    """Bind scheduled-LoRA autocomplete context to the composed coordinator."""

    def __init__(self) -> None:
        """Initialize an unbound current-context bridge."""

        self._current_context: PromptAutocompleteScheduledLoraCurrentContext | None = (
            None
        )

    def bind(
        self,
        current_context: PromptAutocompleteScheduledLoraCurrentContext,
    ) -> None:
        """Attach the live autocomplete current-context provider."""

        self._current_context = current_context

    def current_source_identity(self) -> PromptSourceIdentity | None:
        """Return the bound autocomplete source identity."""

        if self._current_context is None:
            return None
        return self._current_context.current_source_identity()

    def current_query_identity(self) -> Hashable | None:
        """Return the bound autocomplete query identity."""

        if self._current_context is None:
            return None
        return self._current_context.current_query_identity()

    def refresh_current_query(self) -> None:
        """Refresh the bound autocomplete query when available."""

        if self._current_context is not None:
            self._current_context.refresh_current_query()


__all__ = ["PromptAutocompleteCurrentContextBridge"]
