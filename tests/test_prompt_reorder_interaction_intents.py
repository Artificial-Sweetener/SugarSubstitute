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

"""Verify typed reorder interaction intent publication."""

from __future__ import annotations

from PySide6.QtCore import QPoint

from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderCancelIntent,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderDragIntent,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_intents import (
    PromptReorderInteractionIntentOwner,
)


def test_interaction_intent_owner_replaces_and_disconnects_handlers() -> None:
    """Optional host ports should have one replaceable publication owner."""

    owner = PromptReorderInteractionIntentOwner()
    received: list[PromptReorderDragIntent] = []
    intent = PromptReorderDragIntent(
        phase="move",
        segment_index=3,
        global_position=QPoint(10, 20),
    )

    owner.publish_drag(intent)
    owner.set_drag_handler(received.append)
    owner.publish_drag(intent)
    owner.set_drag_handler(None)
    owner.publish_drag(intent)

    assert received == [intent]


def test_interaction_intent_owner_preserves_unused_cancel_port() -> None:
    """The public cancel port should remain typed even before a producer uses it."""

    owner = PromptReorderInteractionIntentOwner()
    received: list[PromptReorderCancelIntent] = []
    intent = PromptReorderCancelIntent(reason="escape")

    owner.set_cancel_handler(received.append)
    owner.publish_cancel(intent)

    assert received == [intent]
