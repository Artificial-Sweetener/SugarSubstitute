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

"""Contracts for LoRA picker folder routing and filter composition."""

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.overlays import PromptLoraPickerPopup
from substitute.presentation.widgets.folder_route import FolderRouteBar
from substitute.presentation.widgets.model_picker import ModelPickerWallView

from .support import (
    _CountingAssetRepository,
    _click_route_button,
    _item,
    _item_with_basename,
    _top_screen_anchor_rect,
    _wall_titles,
    ensure_qapp,
)


def test_lora_picker_filter_rebuilds_wall_without_thumbnail_loads() -> None:
    """Filtering should use cheap search text and avoid thumbnail asset reads."""

    ensure_qapp()
    asset_repository = _CountingAssetRepository()
    popup = PromptLoraPickerPopup(
        (_item("Mineru", "illustrious character mineru"), _item("Other", "pony")),
        thumbnail_cache=PromptLoraThumbnailCache(asset_repository),
    )

    popup._search.setText("mineru")

    assert len(popup._view.items()) == 1
    assert popup._view.items()[0].title == "Mineru"
    assert asset_repository.reads == 0


def test_lora_picker_route_ui_sits_between_search_and_wall() -> None:
    """The picker should place route controls below search and above the wall."""

    ensure_qapp()
    popup = PromptLoraPickerPopup(
        (_item("Mineru", "mineru"),),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )
    layout = popup._frame.content_layout()

    search_item = layout.itemAt(0)
    route_item = layout.itemAt(1)
    wall_item = layout.itemAt(2)
    assert search_item is not None
    assert route_item is not None
    assert wall_item is not None
    assert search_item.widget() is popup._search
    assert isinstance(route_item.widget(), FolderRouteBar)
    assert isinstance(wall_item.widget(), ModelPickerWallView)


def test_lora_picker_route_filters_by_folder_and_breadcrumb_restores_root() -> None:
    """Folder route clicks should narrow wall items and breadcrumb root should reset."""

    app = ensure_qapp()
    popup = PromptLoraPickerPopup(
        (
            _item_with_basename(
                "Midna",
                "midna",
                basename="Midna",
                folder=r"illustrious\characters",
            ),
            _item_with_basename(
                "Illustrious Style",
                "style",
                basename="Style",
                folder="illustrious/style",
            ),
            _item_with_basename(
                "Pony",
                "pony",
                basename="Pony",
                folder="pony",
            ),
        ),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )
    popup.show()
    app.processEvents()

    assert _wall_titles(popup) == ["Midna", "Illustrious Style", "Pony"]

    _click_route_button(popup, "illustrious (2)")
    app.processEvents()

    assert _wall_titles(popup) == ["Midna", "Illustrious Style"]

    _click_route_button(popup, "characters (1)")
    app.processEvents()

    assert _wall_titles(popup) == ["Midna"]

    breadcrumb = popup._route_bar._breadcrumb
    QTest.mouseClick(breadcrumb.itemAt(0), Qt.MouseButton.LeftButton)
    app.processEvents()

    assert _wall_titles(popup) == ["Midna", "Illustrious Style", "Pony"]


def test_lora_picker_route_and_search_filters_compose_without_clearing_state() -> None:
    """Search and route changes should preserve each other while filtering."""

    app = ensure_qapp()
    popup = PromptLoraPickerPopup(
        (
            _item_with_basename(
                "Midna",
                "character midna",
                basename="Midna",
                folder="illustrious/characters",
            ),
            _item_with_basename(
                "Style",
                "style illustrious",
                basename="Style",
                folder="illustrious/style",
            ),
            _item_with_basename(
                "Pony Style",
                "style pony",
                basename="PonyStyle",
                folder="pony",
            ),
        ),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )
    popup.show()
    app.processEvents()

    _click_route_button(popup, "illustrious (2)")
    popup._search.setText("style")
    app.processEvents()

    assert popup._route_bar.current_route() == ("illustrious",)
    assert _wall_titles(popup) == ["Style"]

    breadcrumb = popup._route_bar._breadcrumb
    QTest.mouseClick(breadcrumb.itemAt(0), Qt.MouseButton.LeftButton)
    app.processEvents()

    assert popup._search.text() == "style"
    assert _wall_titles(popup) == ["Style", "Pony Style"]

    _click_route_button(popup, "illustrious (2)")
    popup._search.clear()
    app.processEvents()

    assert popup._route_bar.current_route() == ("illustrious",)
    assert _wall_titles(popup) == ["Midna", "Style"]


def test_lora_picker_route_changes_do_not_load_thumbnails() -> None:
    """Route building, route clicks, and active-route search should avoid thumbnails."""

    ensure_qapp()
    asset_repository = _CountingAssetRepository()
    popup = PromptLoraPickerPopup(
        (
            _item_with_basename(
                "Midna",
                "midna",
                basename="Midna",
                folder="illustrious/characters",
            ),
            _item_with_basename(
                "Pony",
                "pony",
                basename="Pony",
                folder="pony",
            ),
        ),
        thumbnail_cache=PromptLoraThumbnailCache(asset_repository),
    )
    popup._set_active_route(("illustrious",))
    popup._search.setText("midna")

    assert _wall_titles(popup) == ["Midna"]
    assert asset_repository.reads == 0


def test_lora_picker_route_button_focus_still_allows_escape_close() -> None:
    """Escape should still close after clicking a child route button."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    popup = PromptLoraPickerPopup(
        (
            _item_with_basename(
                "Midna",
                "midna",
                basename="Midna",
                folder="illustrious/characters",
            ),
            _item_with_basename(
                "Pony",
                "pony",
                basename="Pony",
                folder="pony",
            ),
        ),
        thumbnail_cache=PromptLoraThumbnailCache(),
        parent=host,
    )
    popup.show_attached_to(_top_screen_anchor_rect())
    app.processEvents()

    _click_route_button(popup, "illustrious (1)")
    app.processEvents()
    assert popup.isVisible() is True

    focus_widget = QApplication.focusWidget()
    assert focus_widget is not None
    QTest.keyClick(focus_widget, Qt.Key.Key_Escape)
    app.processEvents()

    assert popup.isVisible() is False
    popup.deleteLater()
    host.deleteLater()


def test_lora_picker_wall_navigation_still_works_after_route_change() -> None:
    """The wall should keep keyboard-style navigation after route filtering."""

    ensure_qapp()
    popup = PromptLoraPickerPopup(
        (
            _item_with_basename(
                "Midna",
                "midna",
                basename="Midna",
                folder="illustrious/characters",
            ),
            _item_with_basename(
                "Style",
                "style",
                basename="Style",
                folder="illustrious/style",
            ),
            _item_with_basename(
                "Pony",
                "pony",
                basename="Pony",
                folder="pony",
            ),
        ),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )

    popup._set_active_route(("illustrious",))
    popup._view.move_current_right()

    assert popup._view.current_index() == 1
    assert popup._view.current_payload() is popup._view.picker_items()[1]
