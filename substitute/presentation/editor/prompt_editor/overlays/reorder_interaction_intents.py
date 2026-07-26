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

"""Own optional reorder interaction intent publication."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
)

from .reorder_gesture_controller import PromptReorderDragIntent


class PromptReorderInteractionIntentOwner:
    """Own host callback lifecycle for typed reorder intents."""

    def __init__(self) -> None:
        """Initialize disconnected intent ports."""

        self._drag_handler: Callable[[PromptReorderDragIntent], None] | None = None
        self._commit_handler: Callable[[PromptReorderCommitIntent], None] | None = None
        self._cancel_handler: Callable[[PromptReorderCancelIntent], None] | None = None

    def set_drag_handler(
        self,
        handler: Callable[[PromptReorderDragIntent], None] | None,
    ) -> None:
        """Replace the optional drag-intent consumer."""

        self._drag_handler = handler

    def set_commit_handler(
        self,
        handler: Callable[[PromptReorderCommitIntent], None] | None,
    ) -> None:
        """Replace the optional commit-intent consumer."""

        self._commit_handler = handler

    def set_cancel_handler(
        self,
        handler: Callable[[PromptReorderCancelIntent], None] | None,
    ) -> None:
        """Replace the optional cancel-intent consumer."""

        self._cancel_handler = handler

    def publish_drag(self, intent: PromptReorderDragIntent) -> None:
        """Publish a drag intent when a consumer is connected."""

        if self._drag_handler is not None:
            self._drag_handler(intent)

    def publish_commit(self, intent: PromptReorderCommitIntent) -> None:
        """Publish a commit intent when a consumer is connected."""

        if self._commit_handler is not None:
            self._commit_handler(intent)

    def publish_cancel(self, intent: PromptReorderCancelIntent) -> None:
        """Publish a cancel intent when a consumer is connected."""

        if self._cancel_handler is not None:
            self._cancel_handler(intent)
