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

"""Contract tests for the editor-attached LoRA picker popup."""

from __future__ import annotations

import os
from typing import cast
from uuid import UUID

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QWidget
from qfluentwidgets import SearchLineEdit  # type: ignore[import-untyped]

from substitute.application.prompt_editor import (
    PromptLoraCatalogItem,
    PromptLoraThumbnailVariant,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_ROLE,
    STANDARD_THUMBNAIL_ROLE,
)
from substitute.presentation.widgets.fluent_popup_frame import (
    AttachedFluentPopupFrame,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptLoraPickerPopup,
    PromptLoraWallView,
    lora_item_aspect_ratio,
    wall_items_for_loras,
)
from substitute.presentation.widgets.model_picker import (
    ModelPickerPopupPlacementMode,
    ModelPickerWallView,
)
from substitute.presentation.widgets.folder_route import FolderRouteBar
from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "editor-attached QFluent picker widget tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _CountingAssetRepository:
    """Count thumbnail asset reads without returning assets."""

    def __init__(self) -> None:
        """Initialize the fake repository call counter."""

        self.reads = 0

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Record thumbnail access and return no asset."""

        _ = storage_key
        self.reads += 1
        return None


class _MetadataActionHandler:
    """Record LoRA picker metadata action targets."""

    def __init__(self) -> None:
        """Prepare refresh observations."""

        self.refresh_targets: list[object] = []

    def refresh_civitai_metadata(self, target: object) -> None:
        """Record one refresh target."""

        self.refresh_targets.append(target)

    def output_canvas_thumbnail_choices(
        self,
    ) -> tuple[OutputCanvasThumbnailChoice, ...]:
        """Return no output choices for existing picker tests."""

        return ()

    def active_output_canvas_thumbnail_choice(
        self,
    ) -> OutputCanvasThumbnailChoice | None:
        """Return no active output choice for existing picker tests."""

        return None

    def set_thumbnail_from_output_image(
        self,
        target: ModelMetadataContextMenuTarget,
        image_id: UUID,
    ) -> None:
        """Ignore output thumbnail requests in existing picker tests."""

        _ = (target, image_id)


def ensure_qapp() -> QApplication:
    """Return a running Qt application for picker model tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _actions(items: tuple[object, ...]) -> tuple[ModelMetadataMenuAction, ...]:
    """Return action items from one menu item tuple."""

    return tuple(item for item in items if isinstance(item, ModelMetadataMenuAction))


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


def test_lora_picker_wall_uses_display_name_title_and_subtitle() -> None:
    """The wall title and subtitle should come from catalog display fields."""

    ensure_qapp()
    popup = PromptLoraPickerPopup(
        (
            _item_with_basename(
                "CivitAI Midna",
                "midna",
                basename="Midna",
                display_subtitle="v2.0",
            ),
        ),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )

    assert popup._view.items()[0].title == "CivitAI Midna"
    assert popup._view.items()[0].subtitle == "v2.0"


def test_lora_picker_wall_omits_missing_display_subtitle() -> None:
    """The wall should keep subtitle empty when the catalog has no subtitle."""

    wall_item = wall_items_for_loras((_item("Local Midna", "midna"),))[0]

    assert wall_item.title == "Local Midna"
    assert wall_item.subtitle is None


def test_lora_picker_popup_emits_catalog_item_from_shared_wall() -> None:
    """The picker should activate the catalog payload rendered by the shared wall."""

    ensure_qapp()
    item = _item("Mineru", "mineru")
    popup = PromptLoraPickerPopup(
        (item,),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )
    activated: list[object] = []
    popup.loraActivated.connect(activated.append)

    assert popup._view.activate_current() is True

    assert activated == [item]


def test_lora_picker_popup_set_loras_updates_rows_without_resetting_search() -> None:
    """Live LoRA metadata refresh should update an open popup in place."""

    ensure_qapp()
    popup = PromptLoraPickerPopup(
        (_item("Midna", "midna"),),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )
    popup.set_search_text("mineru")

    popup.set_loras((_item("Mineru", "mineru"),))

    current_item = popup.current_item()
    assert popup.search_text() == "mineru"
    assert current_item is not None
    assert current_item.title == "Mineru"


def test_lora_wall_uses_only_standard_thumbnail_variants() -> None:
    """The picker wall should not use banner variants for tile thumbnails."""

    item = _item_with_basename(
        "CivitAI Midna",
        "midna",
        basename="Midna",
        thumbnail_variants=(
            PromptLoraThumbnailVariant(
                size=128,
                storage_key="midna:standard:128",
                width=85,
                height=128,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=43520,
                role=STANDARD_THUMBNAIL_ROLE,
            ),
            PromptLoraThumbnailVariant(
                size=768,
                storage_key="midna:banner:768x160",
                width=768,
                height=160,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=491520,
                role=BANNER_THUMBNAIL_ROLE,
            ),
        ),
    )

    wall_item = wall_items_for_loras((item,))[0]

    assert [variant.role for variant in wall_item.thumbnail_variants] == [
        STANDARD_THUMBNAIL_ROLE
    ]
    assert wall_item.thumbnail_variants[0].storage_key == "midna:standard:128"
    assert lora_item_aspect_ratio(item) == 85 / 128


def test_lora_wall_items_carry_relative_path_tooltips() -> None:
    """The LoRA wall should expose model relative paths as tile tooltips."""

    item = _item_with_basename(
        "CivitAI Midna",
        "midna",
        basename="Midna",
    )

    wall_item = wall_items_for_loras((item,))[0]

    assert wall_item.tooltip == "Folder/Midna.safetensors"


def test_lora_wall_metadata_menu_action_opens_catalog_url() -> None:
    """The LoRA wall should use the shared metadata CivitAI action."""

    ensure_qapp()
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record opened URLs without launching a browser."""

        opened_urls.append(url)
        return True

    wall = PromptLoraWallView(
        thumbnail_cache=PromptLoraThumbnailCache(),
        open_url=open_url,
    )
    item = _item_with_basename(
        "CivitAI Midna",
        "midna",
        basename="Midna",
        model_page_url="https://civitai.com/models/100?modelVersionId=200",
    )
    wall.set_loras((item,))
    picker_item = wall.picker_items()[0]

    target = wall._metadata_context_menu_target(picker_item)

    assert target is not None
    actions = _actions(wall._metadata_context_menu.menu_items_for_target(target))
    assert len(actions) == 1
    action = actions[0]
    assert action.label == "Go to CivitAI page"
    action.callback()
    assert opened_urls == ["https://civitai.com/models/100?modelVersionId=200"]


def test_lora_wall_omits_metadata_menu_action_without_url() -> None:
    """The LoRA wall should not expose metadata actions for local-only items."""

    ensure_qapp()
    wall = PromptLoraWallView(
        thumbnail_cache=PromptLoraThumbnailCache(),
        open_url=lambda _url: True,
    )
    wall.set_loras((_item("Local Midna", "midna"),))
    target = wall._metadata_context_menu_target(wall.picker_items()[0])

    assert target is not None
    assert wall._metadata_context_menu.menu_items_for_target(target) == ()


def test_lora_picker_popup_civitai_action_uses_injected_opener() -> None:
    """The LoRA picker popup should pass CivitAI actions to the injected opener."""

    ensure_qapp()
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record opened URLs without launching a browser."""

        opened_urls.append(url)
        return True

    item = _item_with_basename(
        "CivitAI Midna",
        "midna",
        basename="Midna",
        model_page_url="https://civitai.com/models/100?modelVersionId=200",
    )
    popup = PromptLoraPickerPopup(
        (item,),
        thumbnail_cache=PromptLoraThumbnailCache(),
        open_url=open_url,
    )
    target = popup._view._metadata_context_menu_target(popup._view.picker_items()[0])

    assert target is not None
    actions = _actions(popup._view._metadata_context_menu.menu_items_for_target(target))
    assert len(actions) == 1
    action = actions[0]
    action.callback()
    assert opened_urls == ["https://civitai.com/models/100?modelVersionId=200"]


def test_lora_picker_popup_refresh_action_targets_lora_metadata() -> None:
    """LoRA picker refresh actions should target the selected LoRA identity."""

    ensure_qapp()
    handler = _MetadataActionHandler()
    item = _item_with_basename("CivitAI Midna", "midna", basename="Midna")
    popup = PromptLoraPickerPopup(
        (item,),
        thumbnail_cache=PromptLoraThumbnailCache(),
        metadata_action_handler=handler,
    )
    target = popup._view._metadata_context_menu_target(popup._view.picker_items()[0])

    assert target is not None
    actions = _actions(popup._view._metadata_context_menu.menu_items_for_target(target))
    assert [action.label for action in actions] == [
        "Refresh CivitAI metadata",
        "Set thumbnail from canvas",
    ]
    actions[0].callback()
    assert len(handler.refresh_targets) == 1
    refresh_target = handler.refresh_targets[0]
    assert getattr(refresh_target, "model_kind") == "loras"
    assert getattr(refresh_target, "backend_value") == "Folder/Midna.safetensors"


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


def _item(display_name: str, search_text: str) -> PromptLoraCatalogItem:
    """Return one picker-ready LoRA catalog item."""

    return _item_with_basename(display_name, search_text, basename=display_name)


def _item_with_basename(
    display_name: str,
    search_text: str,
    *,
    basename: str,
    folder: str = "Folder",
    thumbnail_variants: tuple[PromptLoraThumbnailVariant, ...] | None = None,
    model_page_url: str | None = None,
    display_subtitle: str | None = None,
) -> PromptLoraCatalogItem:
    """Return one picker-ready LoRA catalog item with an explicit basename."""

    normalized_folder = folder.replace("\\", "/")
    relative_path = (
        f"{normalized_folder}/{basename}.safetensors"
        if folder
        else f"{basename}.safetensors"
    )
    return PromptLoraCatalogItem(
        display_name=display_name,
        display_subtitle=display_subtitle,
        prompt_name=relative_path.removesuffix(".safetensors"),
        backend_value=relative_path,
        relative_path=relative_path,
        folder=folder,
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=thumbnail_variants
        if thumbnail_variants is not None
        else (
            PromptLoraThumbnailVariant(
                size=128,
                storage_key=f"{basename}:128",
                width=85,
                height=128,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=43520,
                role=STANDARD_THUMBNAIL_ROLE,
            ),
        ),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=model_page_url,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=search_text,
    )


def _wall_titles(popup: PromptLoraPickerPopup) -> list[str]:
    """Return currently visible LoRA wall titles."""

    return [item.title for item in popup._view.items()]


def _click_route_button(popup: PromptLoraPickerPopup, text: str) -> None:
    """Click one visible route button by text."""

    for button in popup._route_bar.child_route_buttons():
        if button.text() == text:
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            return
    raise AssertionError(f"Missing route button: {text}")


def _anchor_rect(x: int, y: int) -> QRect:
    """Return a point-like global popup anchor rectangle."""

    return QRect(QPoint(x, y), QSize(1, 1))


def _top_screen_anchor_rect(x_offset: int = 24) -> QRect:
    """Return a point-like global anchor near the top of the available screen."""

    screen = _screen_available_geometry()
    return QRect(
        QPoint(screen.left() + x_offset, screen.top() + 24),
        QSize(1, 1),
    )


def _bottom_screen_anchor_rect() -> QRect:
    """Return a point-like global anchor near the bottom of the available screen."""

    screen = _screen_available_geometry()
    return QRect(
        QPoint(screen.left() + 100, screen.top() + screen.height() - 40),
        QSize(1, 1),
    )


def _screen_available_geometry() -> QRect:
    """Return the primary screen's available geometry for global-anchor tests."""

    app = ensure_qapp()
    screen = app.primaryScreen()
    if screen is None:
        return QRect(0, 0, 1920, 1080)
    return screen.availableGeometry()


def _visible_layout_widgets(popup: PromptLoraPickerPopup) -> list[QWidget]:
    """Return visible widgets in the popup content layout order."""

    layout = popup._frame.content_layout()
    widgets: list[QWidget] = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None and not widget.isHidden():
            widgets.append(widget)
    return widgets
