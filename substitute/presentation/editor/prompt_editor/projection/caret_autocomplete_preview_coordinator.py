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

"""Coordinate autocomplete preview state after projection caret changes."""

from __future__ import annotations

from typing import Protocol

from ..debug_probe import log_prompt_editor_probe, preview_probe_state
from ..autocomplete_preview_state import PromptAutocompletePreviewState


class PromptCaretAutocompletePreviewHost(Protocol):
    """Expose preview operations needed after caret movement."""

    def current_autocomplete_preview_state(
        self,
    ) -> PromptAutocompletePreviewState | None:
        """Return current projection-owned autocomplete preview state."""

    def clear_autocomplete_preview_state(self) -> None:
        """Clear autocomplete preview through the authoritative preview owner."""

    def rebuild_active_projection_for_autocomplete_preview(self) -> None:
        """Rebuild active projection after preview/caret reconciliation."""


class PromptCaretAutocompletePreviewCoordinator:
    """Keep caret movement from leaving stale autocomplete preview projection."""

    def __init__(self, host: PromptCaretAutocompletePreviewHost) -> None:
        """Store the projection host controlled by this coordinator."""

        self._host = host

    def reconcile_after_caret_state_change(
        self,
        *,
        cursor_position: int,
        selection_is_empty: bool,
    ) -> None:
        """Clear or rebuild preview projection after committed caret movement."""

        preview_state = self._host.current_autocomplete_preview_state()
        log_prompt_editor_probe(
            "caret_autocomplete_preview.reconcile.begin",
            coordinator_id=id(self),
            cursor_position=cursor_position,
            selection_is_empty=selection_is_empty,
            preview=preview_probe_state(preview_state),
        )
        if preview_state is None:
            log_prompt_editor_probe(
                "caret_autocomplete_preview.reconcile.end",
                coordinator_id=id(self),
                action="noop_no_preview",
            )
            return
        if not selection_is_empty or preview_state.source_position != cursor_position:
            self._host.clear_autocomplete_preview_state()
            log_prompt_editor_probe(
                "caret_autocomplete_preview.reconcile.end",
                coordinator_id=id(self),
                action="clear",
            )
            return
        self._host.rebuild_active_projection_for_autocomplete_preview()
        log_prompt_editor_probe(
            "caret_autocomplete_preview.reconcile.end",
            coordinator_id=id(self),
            action="rebuild",
        )


__all__ = [
    "PromptCaretAutocompletePreviewCoordinator",
    "PromptCaretAutocompletePreviewHost",
]
