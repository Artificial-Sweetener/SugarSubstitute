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

"""Define prepared-state contracts for prompt autocomplete overlays."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)


@dataclass(frozen=True, slots=True)
class PromptAutocompleteRowRenderState:
    """Describe one prepared autocomplete row for overlay rendering."""

    index: int
    title: str
    detail: str | None = None
    source_label: str | None = None
    is_selected: bool = False
    is_hovered: bool = False
    payload: object | None = None


@dataclass(frozen=True, slots=True)
class PromptAutocompleteLoraWallRenderState:
    """Describe prepared LoRA wall content embedded in autocomplete chrome."""

    items: tuple[PromptLoraCatalogItem, ...]
    selected_index: int
    activation_payloads: tuple[object | None, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptAutocompletePanelRenderState:
    """Describe the complete prepared autocomplete panel view state."""

    rows: tuple[PromptAutocompleteRowRenderState, ...] = ()
    lora_wall: PromptAutocompleteLoraWallRenderState | None = None
    visible: bool = False
    anchor_rect: QRect | None = None
    minimum_size: QSize | None = None


@dataclass(frozen=True, slots=True)
class PromptAutocompleteActivationIntent:
    """Describe an autocomplete item activation emitted by the overlay."""

    index: int
    payload: object | None = None


class PromptAutocompleteOverlay(Protocol):
    """Render prepared autocomplete state and relay selection intent."""

    def set_render_state(self, state: PromptAutocompletePanelRenderState) -> None:
        """Replace the prepared state rendered by the autocomplete overlay."""

    def set_activation_handler(
        self,
        handler: Callable[[PromptAutocompleteActivationIntent], None] | None,
    ) -> None:
        """Set the callback used when the user activates a prepared item."""

    def set_selection_changed_handler(
        self,
        handler: Callable[[int], None] | None,
    ) -> None:
        """Set the callback used when overlay navigation changes selection."""

    def current_index(self) -> int:
        """Return the currently highlighted prepared item index."""

    def set_current_index(self, index: int) -> None:
        """Highlight one prepared item without accepting it."""

    def preferred_size(self) -> QSize:
        """Return the overlay's preferred size for the current render state."""

    def show_overlay(self, anchor_rect: QRect) -> None:
        """Show the overlay at the prepared editor-relative anchor rect."""

    def hide_overlay(self) -> None:
        """Hide the overlay without mutating editor source."""

    def is_panel_visible(self) -> bool:
        """Return whether the autocomplete panel is currently visible."""

    def set_visibility_changed_handler(
        self,
        handler: Callable[[bool], None] | None,
    ) -> None:
        """Set the callback used when overlay visibility changes."""


class PromptAutocompleteLoraActivationSignal(Protocol):
    """Describe the Qt signal used to relay LoRA wall activation."""

    def connect(self, slot: Callable[[object], object]) -> object:
        """Connect one activation callback."""


class PromptAutocompleteLoraWall(Protocol):
    """Describe the LoRA wall behavior consumed by autocomplete presentation."""

    loraActivated: PromptAutocompleteLoraActivationSignal

    def set_loras(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Replace the LoRA items rendered by the wall."""

    def set_current_index(self, index: int) -> None:
        """Highlight one prepared LoRA candidate."""

    def current_index(self) -> int:
        """Return the highlighted LoRA candidate index."""

    def move_current_left(self) -> None:
        """Move the highlighted LoRA candidate left."""

    def move_current_right(self) -> None:
        """Move the highlighted LoRA candidate right."""

    def move_current_up(self) -> None:
        """Move the highlighted LoRA candidate up."""

    def move_current_down(self) -> None:
        """Move the highlighted LoRA candidate down."""

    def activate_current(self) -> bool:
        """Activate the currently highlighted LoRA candidate."""

    def show(self) -> None:
        """Show the wall widget."""

    def hide(self) -> None:
        """Hide the wall widget."""

    def setParent(self, parent: QWidget | None) -> None:  # noqa: N802
        """Reparent the wall widget while preserving Qt ownership."""


__all__ = [
    "PromptAutocompleteActivationIntent",
    "PromptAutocompleteLoraActivationSignal",
    "PromptAutocompleteLoraWall",
    "PromptAutocompleteLoraWallRenderState",
    "PromptAutocompleteOverlay",
    "PromptAutocompletePanelRenderState",
    "PromptAutocompleteRowRenderState",
]
