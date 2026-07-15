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

"""Adapt Input QPane display APIs for guarded route projectors."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.qpane.input_pane_adapter")


class _InputDisplayPane(Protocol):
    """Describe Input QPane display methods used by the route adapter."""

    def setCurrentImageID(self, image_id: UUID | None) -> None:  # noqa: N802
        """Switch the active image selection."""

    def currentImageID(self) -> UUID | None:  # noqa: N802
        """Return the active image selection."""

    def setActiveMaskID(self, mask_id: UUID) -> None:  # noqa: N802
        """Switch the active mask layer."""


class InputQPaneRouteAdapter:
    """Wrap one Input QPane instance with display-only operations."""

    def __init__(self, pane: object) -> None:
        """Store the wrapped Input QPane."""

        self._pane = pane

    def set_current_image_id(self, image_id: UUID | None) -> bool:
        """Set the active image through QPane's public display API."""

        setter = getattr(self._pane, "setCurrentImageID", None)
        if not callable(setter):
            log_warning(
                _LOGGER,
                "Input QPane route selection skipped because API is unavailable",
                image_id=image_id,
            )
            return False
        setter(image_id)
        return True

    def current_image_id(self) -> UUID | None:
        """Return the active image through QPane's public display API."""

        getter = getattr(self._pane, "currentImageID", None)
        if not callable(getter):
            return None
        value = getter()
        return value if isinstance(value, UUID) else None

    def set_active_mask_id(self, mask_id: UUID) -> bool:
        """Set the active mask through QPane's public display API."""

        setter = getattr(self._pane, "setActiveMaskID", None)
        if not callable(setter):
            log_warning(
                _LOGGER,
                "Input QPane route mask activation skipped because API is unavailable",
                mask_id=mask_id,
            )
            return False
        setter(mask_id)
        return True


__all__ = ["InputQPaneRouteAdapter"]
