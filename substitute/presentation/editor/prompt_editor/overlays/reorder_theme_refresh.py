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

"""Describe immutable inputs used by reorder theme refreshes."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.document.views import PromptReorderChipView

from .reorder_gesture_controller import PromptReorderGestureStateView


@dataclass(frozen=True, slots=True)
class PromptReorderThemeRefreshRequest:
    """Describe the prepared drag-proxy facts relevant to a theme refresh."""

    has_document: bool
    dragged_segment: PromptReorderChipView | None
    source_revision: int | None
    gesture: PromptReorderGestureStateView
    gesture_id: int | None
    event_id: int | None


__all__ = ["PromptReorderThemeRefreshRequest"]
