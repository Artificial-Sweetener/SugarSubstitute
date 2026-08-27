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

"""Contracts for LoRA picker popup window behavior and placement."""

from __future__ import annotations


from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QWidget
from qfluentwidgets import SearchLineEdit  # type: ignore[import-untyped]

from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.overlays import PromptLoraPickerPopup
from substitute.presentation.widgets.fluent_popup_frame import (
    AttachedFluentPopupFrame,
)
from substitute.presentation.widgets.model_picker import ModelPickerPopupPlacementMode

from .support import (
    _bottom_screen_anchor_rect,
    _item,
    _top_screen_anchor_rect,
    _visible_layout_widgets,
    ensure_qapp,
)


def test_lora_picker_popup_is_popup_window_not_dialog() -> None:
    """The picker surface should be a top-level popup, not a dialog."""

    ensure_qapp()
    host = QWidget()
    popup = PromptLoraPickerPopup(
        (_item("Mineru", "mineru"),),
        thumbnail_cache=PromptLoraThumbnailCache(),
        parent=host,
    )

    assert popup.parentWidget() is host
    assert popup.windowFlags() & Qt.WindowType.Popup
    assert not isinstance(popup, QDialog)


def test_lora_picker_popup_uses_qfluent_search_and_shared_frame() -> None:
    """The picker should use real QFluent widgets for search and popup chrome."""

    ensure_qapp()
    host = QWidget()
    popup = PromptLoraPickerPopup(
        (_item("Mineru", "mineru"),),
        thumbnail_cache=PromptLoraThumbnailCache(),
        parent=host,
    )

    assert isinstance(popup._search, SearchLineEdit)
    assert isinstance(popup._frame, AttachedFluentPopupFrame)
    assert popup._search.isHidden() is False
    search_item = popup._frame.content_layout().itemAt(0)
    assert search_item is not None
    assert search_item.widget() is popup._search
    assert popup.styleSheet() == ""
    assert popup.windowFlags() & Qt.WindowType.Popup
    popup.deleteLater()
    host.deleteLater()


def test_lora_picker_popup_above_placement_keeps_search_near_anchor_edge() -> None:
    """Above placement should put embedded search at the bottom of the popup."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 720)
    host.show()
    popup = PromptLoraPickerPopup(
        (_item("Mineru", "mineru"),),
        thumbnail_cache=PromptLoraThumbnailCache(),
        parent=host,
    )

    anchor = _bottom_screen_anchor_rect()

    popup.show_attached_to(anchor)
    app.processEvents()

    assert popup._placement_mode is ModelPickerPopupPlacementMode.ABOVE
    assert popup.geometry().top() + popup.geometry().height() <= anchor.top()
    assert _visible_layout_widgets(popup) == [
        popup._view,
        popup._route_bar,
        popup._search,
    ]
    popup.deleteLater()
    host.deleteLater()


def test_lora_picker_popup_hides_on_escape_from_search_focus() -> None:
    """Escape should close the picker even while the QFluent search owns focus."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    popup = PromptLoraPickerPopup(
        (_item("Mineru", "mineru"),),
        thumbnail_cache=PromptLoraThumbnailCache(),
        parent=host,
    )
    popup.show_attached_to(_top_screen_anchor_rect())
    app.processEvents()

    assert popup.isVisible() is True
    assert QApplication.focusWidget() is popup._search

    search = popup._search
    assert search is not None
    QTest.keyClick(search, Qt.Key.Key_Escape)
    app.processEvents()

    assert popup.isVisible() is False
    popup.deleteLater()
    host.deleteLater()


def test_lora_picker_popup_hides_on_outside_click() -> None:
    """Clicking elsewhere in the editor host should hide the picker."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    popup = PromptLoraPickerPopup(
        (_item("Mineru", "mineru"),),
        thumbnail_cache=PromptLoraThumbnailCache(),
        parent=host,
    )
    popup.show_attached_to(_top_screen_anchor_rect(300))
    app.processEvents()

    assert popup.isVisible() is True

    QTest.mouseClick(host, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
    app.processEvents()

    assert popup.isVisible() is False
    popup.deleteLater()
    host.deleteLater()


def test_lora_picker_popup_uses_taller_shared_menu_size() -> None:
    """The LoRA picker should use the shared taller popup geometry."""

    ensure_qapp()
    popup = PromptLoraPickerPopup(
        tuple(_item(f"LoRA {index}", "lora") for index in range(12)),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )

    assert popup.size().width() == 560
    assert popup.size().height() == 630
    assert popup._view.verticalScrollBar().singleStep() >= 108
