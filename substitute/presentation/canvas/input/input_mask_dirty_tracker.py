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

"""Track unsaved Input mask edits outside the canvas widget."""

from __future__ import annotations

from uuid import UUID

from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("presentation.canvas.input.input_mask_dirty_tracker")


class InputMaskDirtyTracker:
    """Own dirty-mask state for Input mask persistence controllers."""

    def __init__(self) -> None:
        """Initialize empty dirty-mask state."""

        self._dirty_mask_ids: set[UUID] = set()

    def mark_dirty(self, mask_id: object) -> UUID | None:
        """Mark one valid mask identifier dirty and return its UUID."""

        resolved_mask_id = self.resolve_mask_id(mask_id)
        if resolved_mask_id is None:
            log_warning(
                _LOGGER,
                "Ignored dirty-mask mark for invalid mask id",
                mask_id=str(mask_id),
            )
            return None
        self._dirty_mask_ids.add(resolved_mask_id)
        log_debug(
            _LOGGER,
            "Marked input mask dirty",
            mask_id=str(resolved_mask_id),
            dirty=True,
        )
        return resolved_mask_id

    def is_dirty(self, mask_id: object) -> bool:
        """Return whether one valid mask identifier has unsaved edits."""

        resolved_mask_id = self.resolve_mask_id(mask_id)
        if resolved_mask_id is None:
            log_warning(
                _LOGGER,
                "Ignored dirty-mask lookup for invalid mask id",
                mask_id=str(mask_id),
            )
            return False
        return resolved_mask_id in self._dirty_mask_ids

    def mark_persisted(self, mask_id: object, *, path: str, reason: str) -> bool:
        """Clear dirty state for a mask after confirmed persistence."""

        resolved_mask_id = self.resolve_mask_id(mask_id)
        if resolved_mask_id is None:
            log_warning(
                _LOGGER,
                "Ignored dirty-mask clear for invalid mask id",
                mask_id=str(mask_id),
                path=path,
                reason=reason,
            )
            return False
        self._dirty_mask_ids.discard(resolved_mask_id)
        log_debug(
            _LOGGER,
            "Marked input mask persisted",
            mask_id=str(resolved_mask_id),
            path=path,
            reason=reason,
            dirty=False,
        )
        return True

    def clear(self, mask_id: object) -> bool:
        """Remove dirty state for one mask without persistence side effects."""

        resolved_mask_id = self.resolve_mask_id(mask_id)
        if resolved_mask_id is None:
            return False
        self._dirty_mask_ids.discard(resolved_mask_id)
        return True

    @staticmethod
    def resolve_mask_id(mask_id: object) -> UUID | None:
        """Resolve a QPane or workflow mask identifier into UUID form."""

        if isinstance(mask_id, UUID):
            return mask_id
        if isinstance(mask_id, str):
            try:
                return UUID(mask_id)
            except ValueError:
                return None
        return None


__all__ = ["InputMaskDirtyTracker"]
