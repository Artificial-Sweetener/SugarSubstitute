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

"""Adapt token-control pointer activity to editor wheel-intent policy."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QPointF
from PySide6.QtGui import QWheelEvent

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)


class PromptTokenWeightWheelIntentOwner(Protocol):
    """Own token-weight wheel dwell, activation, and accent publication."""

    def record_token_pointer_move(
        self,
        token: PromptProjectionToken,
        global_position: QPointF,
    ) -> None:
        """Record pointer movement over one numeric token."""
        ...

    def activate_token(
        self,
        token: PromptProjectionToken,
        global_position: QPointF,
    ) -> None:
        """Record explicit token activation for focus-required wheel mode."""
        ...

    def token_wheel_is_allowed(
        self,
        token: PromptProjectionToken,
        event: QWheelEvent,
    ) -> bool:
        """Return whether one token may consume wheel input."""
        ...

    def refresh_candidate_from_pointer(
        self,
        candidate: tuple[PromptProjectionToken, QPointF] | None,
    ) -> None:
        """Refresh dwell accent state from the current pointer candidate."""
        ...

    def clear_candidate(self) -> None:
        """Clear token-wheel dwell and accent state."""
        ...


class PromptTokenWeightWheelIntentRouter:
    """Publish resolved pointer candidates through one wheel-intent boundary."""

    def __init__(self, owner: PromptTokenWeightWheelIntentOwner) -> None:
        """Bind pointer candidate publication to its application-level owner."""

        self._owner = owner

    def record_pointer_move(
        self,
        token: PromptProjectionToken | None,
        *,
        fallback_token: PromptProjectionToken | None,
        global_position: QPointF,
    ) -> None:
        """Publish one real pointer move using the best resolved token."""

        candidate = token if token is not None else fallback_token
        if candidate is None:
            self.clear()
            return
        self._owner.record_token_pointer_move(candidate, global_position)
        self._owner.refresh_candidate_from_pointer(
            (candidate, QPointF(global_position))
        )

    def activate(
        self,
        token: PromptProjectionToken,
        global_position: QPointF,
    ) -> None:
        """Publish explicit click activation for one numeric token."""

        self._owner.activate_token(token, global_position)

    def refresh_candidate(
        self,
        token: PromptProjectionToken,
        global_position: QPointF | None,
    ) -> None:
        """Refresh the dwell candidate derived from current control geometry."""

        if global_position is None:
            return
        self._owner.refresh_candidate_from_pointer((token, global_position))

    def clear(self) -> None:
        """Clear any pending or wheel-ready token candidate."""

        self._owner.clear_candidate()

    def wheel_is_allowed(
        self,
        token: PromptProjectionToken,
        event: QWheelEvent,
    ) -> bool:
        """Return whether one token may consume the wheel event."""

        return self._owner.token_wheel_is_allowed(token, event)


__all__ = [
    "PromptTokenWeightWheelIntentOwner",
    "PromptTokenWeightWheelIntentRouter",
]
