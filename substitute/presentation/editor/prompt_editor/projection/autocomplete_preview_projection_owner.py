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

from typing import Protocol

from ..debug_probe import log_prompt_editor_probe, preview_probe_state
from ..autocomplete_preview_state import PromptAutocompletePreviewState


class PromptAutocompletePreviewProjectionHost(Protocol):
    """Expose projection operations needed by autocomplete preview ownership."""

    def current_autocomplete_preview_state(
        self,
    ) -> PromptAutocompletePreviewState | None:
        """Return the projection session's current autocomplete preview state."""

    def set_session_autocomplete_preview_state(
        self,
        preview_state: PromptAutocompletePreviewState | None,
    ) -> None:
        """Replace autocomplete preview state in the projection session."""

    def flush_pending_projection_for_autocomplete_preview(self) -> None:
        """Flush pending projection work before preview is applied."""

    def base_projection_is_stale_for_autocomplete_preview(self) -> bool:
        """Return whether active preview would be layered over stale geometry."""

    def rebuild_base_projection_for_autocomplete_preview(self) -> None:
        """Rebuild base projection before applying autocomplete preview."""

    def rebuild_active_projection_for_autocomplete_preview(self) -> None:
        """Rebuild active projection after preview state changes."""

    def invalidate_autocomplete_preview_paint(self) -> None:
        """Request repaint for pixels that may contain autocomplete preview text."""


class PromptAutocompletePreviewProjectionOwner:
    """Coordinate preview state, projection rebuilds, and repaint invalidation."""

    def __init__(self, host: PromptAutocompletePreviewProjectionHost) -> None:
        """Store the host whose preview projection state this owner controls."""

        self._host = host

    def set_preview_state(
        self,
        preview_state: PromptAutocompletePreviewState | None,
    ) -> None:
        """Replace preview state and guarantee clear paths invalidate paint."""

        host = self._host
        current_preview = host.current_autocomplete_preview_state()
        log_prompt_editor_probe(
            "autocomplete_preview_owner.set_preview_state.begin",
            owner_id=id(self),
            current_preview=preview_probe_state(current_preview),
            next_preview=preview_probe_state(preview_state),
        )
        if current_preview == preview_state:
            if preview_state is None:
                host.invalidate_autocomplete_preview_paint()
            log_prompt_editor_probe(
                "autocomplete_preview_owner.set_preview_state.end",
                owner_id=id(self),
                changed=False,
                next_preview=preview_probe_state(preview_state),
            )
            return
        if preview_state is not None:
            host.flush_pending_projection_for_autocomplete_preview()
            if host.base_projection_is_stale_for_autocomplete_preview():
                host.rebuild_base_projection_for_autocomplete_preview()
        host.set_session_autocomplete_preview_state(preview_state)
        host.rebuild_active_projection_for_autocomplete_preview()
        if preview_state is None:
            host.invalidate_autocomplete_preview_paint()
        log_prompt_editor_probe(
            "autocomplete_preview_owner.set_preview_state.end",
            owner_id=id(self),
            changed=True,
            next_preview=preview_probe_state(preview_state),
        )


__all__ = [
    "PromptAutocompletePreviewProjectionHost",
    "PromptAutocompletePreviewProjectionOwner",
]
