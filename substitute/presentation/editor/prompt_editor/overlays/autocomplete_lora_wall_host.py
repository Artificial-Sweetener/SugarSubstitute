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

"""Own LoRA-wall mounting, navigation, and activation for autocomplete."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtWidgets import QBoxLayout, QWidget

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)

from .autocomplete_contracts import (
    PromptAutocompleteLoraWall,
    PromptAutocompleteLoraWallRenderState,
)


class PromptAutocompleteLoraWallHost:
    """Adapt an injected LoRA wall to autocomplete panel ownership."""

    def __init__(
        self,
        *,
        parent: QWidget,
        layout: QBoxLayout,
        activated: Callable[[int, object | None], None],
        selection_changed: Callable[[int], None],
        clear_content: Callable[[], None],
    ) -> None:
        """Bind wall lifecycle callbacks to one panel content layout."""

        self._parent = parent
        self._layout = layout
        self._activated = activated
        self._selection_changed = selection_changed
        self._clear_content = clear_content
        self._wall: PromptAutocompleteLoraWall | None = None
        self._items: tuple[PromptLoraCatalogItem, ...] = ()
        self._activation_payloads: tuple[object | None, ...] = ()

    def set_wall(self, wall: PromptAutocompleteLoraWall | None) -> None:
        """Replace the mounted wall while preserving explicit Qt ownership."""

        if self._wall is wall:
            return
        if self._wall is not None:
            old_wall = cast(QWidget, self._wall)
            old_wall.hide()
            old_wall.setParent(None)
        self._wall = wall
        self._items = ()
        self._activation_payloads = ()
        if wall is None:
            return
        wall_widget = cast(QWidget, wall)
        wall_widget.setParent(self._parent)
        wall_widget.hide()
        wall.loraActivated.connect(self._activate_item)

    @prompt_editor_work_event(PromptEditorWorkEvent.AUTOCOMPLETE_LORA_WALL_UPDATE)
    def render(self, state: PromptAutocompleteLoraWallRenderState) -> int:
        """Render prepared wall state and return its initial selection index."""

        self._parent.geometry()
        self._activation_payloads = state.activation_payloads
        wall = self._wall
        if wall is None:
            self._items = ()
            self._parent.updateGeometry()
            return -1
        if state.items != self._items:
            self._clear_content()
            wall.set_loras(state.items)
            self._items = state.items
        elif self._layout.indexOf(cast(QWidget, wall)) < 0:
            self._clear_content()
        wall.show()
        wall_widget = cast(QWidget, wall)
        if self._layout.indexOf(wall_widget) < 0:
            self._layout.addWidget(wall_widget)
        self._parent.updateGeometry()
        return 0 if state.items else -1

    def set_current_index(self, index: int) -> int:
        """Set and return the wall's normalized selection index."""

        if self._wall is None:
            return -1
        self._wall.set_current_index(index)
        return self._wall.current_index()

    def current_index(self) -> int:
        """Return the wall selection or -1 when no wall is mounted."""

        if self._wall is None:
            return -1
        return self._wall.current_index()

    def move_current(self, direction: str) -> int:
        """Move selection in one visual direction and publish the result."""

        wall = self._wall
        if wall is None:
            return -1
        movement = {
            "left": wall.move_current_left,
            "right": wall.move_current_right,
            "up": wall.move_current_up,
            "down": wall.move_current_down,
        }.get(direction)
        if movement is None:
            raise ValueError(f"Unsupported LoRA wall direction {direction!r}.")
        movement()
        current_index = wall.current_index()
        self._selection_changed(current_index)
        return current_index

    def widget(self) -> QWidget | None:
        """Return the mounted wall widget without exposing adapter state."""

        if self._wall is None:
            return None
        return cast(QWidget, self._wall)

    def has_content(self) -> bool:
        """Return whether the mounted wall owns visible candidates."""

        return bool(self._items)

    def _activate_item(self, item: object) -> None:
        """Resolve a wall item to its prepared activation payload."""

        if not isinstance(item, PromptLoraCatalogItem):
            return
        for index, lora_item in enumerate(self._items):
            if lora_item is item or lora_item.prompt_name == item.prompt_name:
                payload = (
                    self._activation_payloads[index]
                    if 0 <= index < len(self._activation_payloads)
                    else None
                )
                self._activated(index, payload)
                return


__all__ = ["PromptAutocompleteLoraWallHost"]
