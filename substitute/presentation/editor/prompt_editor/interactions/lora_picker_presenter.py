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

"""Own LoRA picker popup presentation outside the public editor widget."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import PromptLoraCatalogItem

from ..features import PromptLoraPickerSnapshot
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from .command_adapter import PromptContextMenuTextInsertionExecutor


class PromptLoraPickerActivationSignal(Protocol):
    """Describe the popup activation signal used by the picker presenter."""

    def connect(self, slot: Callable[[object], None]) -> object:
        """Connect one activation callback."""


class PromptLoraPickerPopupView(Protocol):
    """Describe the picker popup operations owned by the presenter."""

    loraActivated: PromptLoraPickerActivationSignal

    def isVisible(self) -> bool:  # noqa: N802
        """Return whether the popup is currently visible."""

    def hide(self) -> None:
        """Hide the popup."""

    def deleteLater(self) -> None:  # noqa: N802
        """Schedule popup deletion through Qt."""

    def set_loras(self, items: Iterable[PromptLoraCatalogItem]) -> None:
        """Replace popup LoRA rows while preserving view state."""


class PromptLoraPickerDataSource(Protocol):
    """Describe LoRA picker rows and insertion text prepared by feature owners."""

    @property
    def lora_picker_ready(self) -> bool:
        """Return whether the picker may be opened."""

    @property
    def lora_picker_snapshot(self) -> PromptLoraPickerSnapshot:
        """Return the latest prepared picker rows and readiness state."""

    def schedule_text_for_lora(self, selected_lora: PromptLoraCatalogItem) -> str:
        """Return scheduler-safe source text for one selected LoRA."""


class PromptLoraPickerPopupFactory(Protocol):
    """Create an editor-attached LoRA picker popup."""

    def __call__(
        self,
        parent: QWidget,
        items: Iterable[PromptLoraCatalogItem],
        *,
        thumbnail_cache: PromptLoraThumbnailCache,
        global_position: QPoint,
    ) -> PromptLoraPickerPopupView:
        """Build and show one popup at the requested global position."""


class PromptLoraPickerPopupPresenter:
    """Coordinate LoRA picker popup lifetime and insertion intent."""

    def __init__(
        self,
        *,
        parent: QWidget,
        data_source: PromptLoraPickerDataSource,
        thumbnail_cache: PromptLoraThumbnailCache,
        text_insertion_executor: PromptContextMenuTextInsertionExecutor,
        popup_factory: PromptLoraPickerPopupFactory,
        last_context_menu_global_pos: Callable[[], QPoint | None],
        cursor_global_position: Callable[[], QPoint],
    ) -> None:
        """Store picker collaborators without taking over feature or source state."""

        self._parent = parent
        self._data_source = data_source
        self._thumbnail_cache = thumbnail_cache
        self._text_insertion_executor = text_insertion_executor
        self._popup_factory = popup_factory
        self._last_context_menu_global_pos = last_context_menu_global_pos
        self._cursor_global_position = cursor_global_position
        self._popup: PromptLoraPickerPopupView | None = None

    def open_lora_picker(self) -> None:
        """Open an editor-attached LoRA picker popup when the feature is ready."""

        if not self._data_source.lora_picker_ready:
            return
        self._replace_existing_popup()
        snapshot = self._data_source.lora_picker_snapshot
        popup = self._popup_factory(
            self._parent,
            snapshot.items if snapshot.consumable else (),
            thumbnail_cache=self._thumbnail_cache,
            global_position=self._placement_global_pos(),
        )
        popup.loraActivated.connect(self.insert_lora_schedule)
        self._popup = popup

    def refresh_visible_lora_picker(self) -> bool:
        """Refresh rows for the currently visible picker popup."""

        popup = self._popup
        if popup is None or not popup.isVisible():
            return False
        snapshot = self._data_source.lora_picker_snapshot
        popup.set_loras(snapshot.items if snapshot.consumable else ())
        return True

    def insert_lora_schedule(self, selected_lora: object) -> None:
        """Insert schedule text for one selected LoRA catalog item."""

        if not isinstance(selected_lora, PromptLoraCatalogItem):
            return
        self._text_insertion_executor.insert_context_menu_text(
            self._data_source.schedule_text_for_lora(selected_lora)
        )

    def _replace_existing_popup(self) -> None:
        """Hide and delete any popup previously owned by this presenter."""

        if self._popup is None:
            return
        self._popup.hide()
        self._popup.deleteLater()
        self._popup = None

    def _placement_global_pos(self) -> QPoint:
        """Return the prompt-menu anchor or current cursor position."""

        return self._last_context_menu_global_pos() or self._cursor_global_position()


__all__ = [
    "PromptLoraPickerActivationSignal",
    "PromptLoraPickerDataSource",
    "PromptLoraPickerPopupFactory",
    "PromptLoraPickerPopupPresenter",
    "PromptLoraPickerPopupView",
]
