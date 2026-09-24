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

"""Own autocomplete preview projection state and paint invalidation."""

from __future__ import annotations

from collections.abc import Callable

from ..autocomplete_preview_state import PromptAutocompletePreviewState
from ..debug_probe import log_prompt_editor_probe, preview_probe_state
from .session import PromptProjectionSession


class PromptAutocompletePreviewProjectionOwner:
    """Own preview state, projection rebuilds, caret reconciliation, and repaint."""

    def __init__(
        self,
        *,
        session: PromptProjectionSession,
        flush_pending_projection: Callable[[], None],
        base_projection_is_stale: Callable[[], bool],
        rebuild_base_projection: Callable[[], None],
        rebuild_active_projection: Callable[[], None],
        request_repaint: Callable[[], None],
        surface_state: Callable[[], dict[str, object]],
    ) -> None:
        """Bind the exact projection operations controlled by preview lifecycle."""

        self._session = session
        self._flush_pending_projection = flush_pending_projection
        self._base_projection_is_stale = base_projection_is_stale
        self._rebuild_base_projection = rebuild_base_projection
        self._rebuild_active_projection = rebuild_active_projection
        self._request_repaint = request_repaint
        self._surface_state = surface_state

    @property
    def state(self) -> PromptAutocompletePreviewState | None:
        """Return the active projection-session preview state."""

        return self._session.autocomplete_preview

    def set_preview_state(
        self,
        preview_state: PromptAutocompletePreviewState | None,
    ) -> None:
        """Replace preview state and guarantee clear paths invalidate paint."""

        current_preview = self.state
        log_prompt_editor_probe(
            "autocomplete_preview_owner.set_preview_state.begin",
            owner_id=id(self),
            current_preview=preview_probe_state(current_preview),
            next_preview=preview_probe_state(preview_state),
            surface=self._surface_state(),
        )
        if current_preview == preview_state:
            if preview_state is None:
                self._invalidate_paint()
            log_prompt_editor_probe(
                "autocomplete_preview_owner.set_preview_state.end",
                owner_id=id(self),
                changed=False,
                next_preview=preview_probe_state(preview_state),
                surface=self._surface_state(),
            )
            return
        if preview_state is not None:
            self._flush_pending_projection()
            if self._base_projection_is_stale():
                self._rebuild_base_projection()
        self._session.set_autocomplete_preview(preview_state)
        self._rebuild_active()
        if preview_state is None:
            self._invalidate_paint()
        log_prompt_editor_probe(
            "autocomplete_preview_owner.set_preview_state.end",
            owner_id=id(self),
            changed=True,
            next_preview=preview_probe_state(preview_state),
            surface=self._surface_state(),
        )

    def clear_preview_state(self) -> None:
        """Clear the active preview through the complete owner lifecycle."""

        self.set_preview_state(None)

    def reconcile_after_caret_state_change(
        self,
        *,
        cursor_position: int,
        selection_is_empty: bool,
    ) -> None:
        """Clear preview state that no longer matches the committed caret."""

        preview_state = self.state
        log_prompt_editor_probe(
            "autocomplete_preview_owner.reconcile_caret.begin",
            owner_id=id(self),
            cursor_position=cursor_position,
            selection_is_empty=selection_is_empty,
            preview=preview_probe_state(preview_state),
            surface=self._surface_state(),
        )
        if preview_state is None:
            action = "noop_no_preview"
        elif not selection_is_empty or preview_state.source_position != cursor_position:
            self.clear_preview_state()
            action = "clear"
        else:
            action = "retain"
        log_prompt_editor_probe(
            "autocomplete_preview_owner.reconcile_caret.end",
            owner_id=id(self),
            action=action,
            surface=self._surface_state(),
        )

    def _rebuild_active(self) -> None:
        """Rebuild active preview projection with owner-state diagnostics."""

        log_prompt_editor_probe(
            "autocomplete_preview_owner.rebuild_active_projection",
            owner_id=id(self),
            surface=self._surface_state(),
        )
        self._rebuild_active_projection()

    def _invalidate_paint(self) -> None:
        """Invalidate pixels that can retain cleared autocomplete preview text."""

        log_prompt_editor_probe(
            "autocomplete_preview_owner.invalidate_paint",
            owner_id=id(self),
            surface=self._surface_state(),
        )
        self._request_repaint()


__all__ = ["PromptAutocompletePreviewProjectionOwner"]
