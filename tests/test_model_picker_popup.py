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

"""Contract tests for the reusable metadata-backed model picker popup."""

from __future__ import annotations

import os
from typing import cast
from uuid import UUID

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import SearchLineEdit  # type: ignore[import-untyped]

from substitute.domain.model_metadata import ThumbnailAsset
from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
)
from substitute.presentation.widgets.fluent_popup_frame import AttachedFluentPopupFrame
from substitute.presentation.widgets.folder_route import FolderRouteBar
from substitute.presentation.widgets.media_wall import ThumbnailVariantReference
from substitute.presentation.widgets.model_picker import (
    MODEL_PICKER_POPUP_HEIGHT,
    MODEL_PICKER_POPUP_WIDTH,
    ModelPickerItem,
    ModelPickerPopup,
    ModelPickerPopupPlacementMode,
    ModelPickerWallView,
)
import substitute.presentation.widgets.model_picker.model_picker_popup as model_picker_popup_module

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "attached QFluent picker widget tests require non-xdist execution on Windows",
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
    """Record model-picker metadata action targets."""

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
    """Return a running Qt application for picker widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _actions(items: tuple[object, ...]) -> tuple[ModelMetadataMenuAction, ...]:
    """Return action items from one menu item tuple."""

    return tuple(item for item in items if isinstance(item, ModelMetadataMenuAction))


def test_model_picker_filter_rebuilds_wall_without_thumbnail_loads() -> None:
    """Filtering should use search text and avoid thumbnail asset reads."""

    ensure_qapp()
    asset_repository = _CountingAssetRepository()
    popup = ModelPickerPopup(
        (_item("Checkpoint A", "alpha"), _item("Checkpoint B", "beta")),
        asset_repository=asset_repository,
    )

    popup._search.setText("alpha")

    assert [item.title for item in popup._view.items()] == ["Checkpoint A"]
    assert asset_repository.reads == 0


def test_model_picker_popup_shows_search_field_by_default() -> None:
    """Default popup construction should preserve the LoRA-style embedded search."""

    ensure_qapp()
    popup = ModelPickerPopup((_item("Checkpoint A", "alpha"),))
    layout = popup._frame.content_layout()

    assert isinstance(popup._search, SearchLineEdit)
    assert popup._search.isHidden() is False
    first_item = layout.itemAt(0)
    assert first_item is not None
    assert first_item.widget() is popup._search


def test_model_picker_popup_can_filter_from_hidden_external_search() -> None:
    """Field-driven picker use should hide embedded search while keeping filtering."""

    ensure_qapp()
    popup = ModelPickerPopup(
        (_item("Checkpoint A", "alpha"), _item("Checkpoint B", "beta")),
        show_search_field=False,
    )
    layout = popup._frame.content_layout()

    assert popup._search.isHidden() is True
    first_item = layout.itemAt(0)
    assert first_item is not None
    assert isinstance(first_item.widget(), FolderRouteBar)

    popup.set_search_text("beta")

    assert popup.search_text() == "beta"
    assert [item.title for item in popup._view.items()] == ["Checkpoint B"]


def test_model_picker_route_and_search_filters_compose() -> None:
    """Folder routes and search text should narrow the same visible wall state."""

    app = ensure_qapp()
    popup = ModelPickerPopup(
        (
            _item("Midna", "character midna", folder="illustrious/characters"),
            _item("Style", "style illustrious", folder="illustrious/style"),
            _item("Pony Style", "style pony", folder="pony"),
        )
    )
    popup.show()
    app.processEvents()

    _click_route_button(popup, "illustrious (2)")
    popup._search.setText("style")
    app.processEvents()

    assert popup._route_bar.current_route() == ("illustrious",)
    assert [item.title for item in popup._view.items()] == ["Style"]

    breadcrumb = popup._route_bar._breadcrumb
    QTest.mouseClick(breadcrumb.itemAt(0), Qt.MouseButton.LeftButton)
    app.processEvents()

    assert [item.title for item in popup._view.items()] == ["Style", "Pony Style"]


def test_model_picker_route_and_external_search_filters_compose() -> None:
    """Hidden-search mode should keep route and field query as one filter state."""

    app = ensure_qapp()
    popup = ModelPickerPopup(
        (
            _item("Midna", "character midna", folder="illustrious/characters"),
            _item("Style", "style illustrious", folder="illustrious/style"),
            _item("Pony Style", "style pony", folder="pony"),
        ),
        show_search_field=False,
    )
    popup.show()
    app.processEvents()

    _click_route_button(popup, "illustrious (2)")
    popup.set_search_text("style")
    app.processEvents()

    assert popup._route_bar.current_route() == ("illustrious",)
    assert [item.title for item in popup._view.items()] == ["Style"]

    breadcrumb = popup._route_bar._breadcrumb
    QTest.mouseClick(breadcrumb.itemAt(0), Qt.MouseButton.LeftButton)
    app.processEvents()

    assert [item.title for item in popup._view.items()] == ["Style", "Pony Style"]


def test_model_picker_popup_emits_payload_from_wall_activation() -> None:
    """Popup activation should emit the selected picker item's payload."""

    ensure_qapp()
    payload = object()
    popup = ModelPickerPopup((_item("Model", "model", payload=payload),))
    activated: list[object] = []
    popup.modelActivated.connect(activated.append)

    assert popup._view.activate_current() is True

    assert activated == [payload]


def test_model_picker_popup_exposes_current_model_item() -> None:
    """External search owners should read current item through a typed popup API."""

    ensure_qapp()
    popup = ModelPickerPopup(
        (
            _item("Alpha", "alpha"),
            _item("Beta", "beta"),
        ),
        show_search_field=False,
    )

    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Alpha"

    popup.set_search_text("beta")

    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Beta"


def test_model_picker_popup_embedded_search_routes_arrow_keys_to_wall() -> None:
    """Embedded-search popups should navigate picker tiles with arrow keys."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    popup = ModelPickerPopup(
        tuple(_item(f"Model {index}", f"model {index}") for index in range(12)),
        parent=host,
    )
    popup.show_attached_to(_top_screen_anchor_rect())
    app.processEvents()

    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 0"

    QTest.keyClick(popup._search, Qt.Key.Key_Right)
    app.processEvents()
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 1"

    QTest.keyClick(popup._search, Qt.Key.Key_Left)
    app.processEvents()
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 0"

    QTest.keyClick(popup._search, Qt.Key.Key_Down)
    app.processEvents()
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title != "Model 0"

    popup.deleteLater()
    host.deleteLater()


def test_model_picker_popup_embedded_search_enter_activates_current_item() -> None:
    """Embedded-search popups should activate the keyboard-selected tile."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    popup = ModelPickerPopup(
        (
            _item("Alpha", "alpha"),
            _item("Beta", "beta"),
        ),
        parent=host,
    )
    activated: list[object] = []
    popup.itemActivated.connect(activated.append)
    popup.show_attached_to(_top_screen_anchor_rect())
    app.processEvents()

    QTest.keyClick(popup._search, Qt.Key.Key_Right)
    QTest.keyClick(popup._search, Qt.Key.Key_Return)
    app.processEvents()

    assert len(activated) == 1
    assert isinstance(activated[0], ModelPickerItem)
    assert activated[0].title == "Beta"
    assert popup.isVisible() is False
    popup.deleteLater()
    host.deleteLater()


def test_model_picker_popup_uses_shared_controls_and_size() -> None:
    """The generic picker should own QFluent search, route, wall, and frame chrome."""

    ensure_qapp()
    popup = ModelPickerPopup((_item("Model", "model"),))
    layout = popup._frame.content_layout()

    assert isinstance(popup._search, SearchLineEdit)
    assert isinstance(popup._frame, AttachedFluentPopupFrame)
    route_item = layout.itemAt(1)
    wall_item = layout.itemAt(2)
    assert route_item is not None
    assert wall_item is not None
    assert isinstance(route_item.widget(), FolderRouteBar)
    assert isinstance(wall_item.widget(), ModelPickerWallView)
    assert popup.size().width() == MODEL_PICKER_POPUP_WIDTH
    assert popup.size().height() == MODEL_PICKER_POPUP_HEIGHT


def test_model_picker_popup_uses_manual_dismissal_window_type() -> None:
    """Model picker popup should not use Qt.Popup native outside-click dismissal."""

    app = ensure_qapp()
    popup = ModelPickerPopup((_item("Model", "model"),))
    flags = popup.windowFlags()
    window_type = flags & Qt.WindowType.WindowType_Mask

    assert window_type == Qt.WindowType.Tool
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.NoDropShadowWindowHint

    popup.deleteLater()
    app.processEvents()


def test_model_picker_popup_below_order_keeps_controls_on_top() -> None:
    """Below placement should keep search and breadcrumbs above the wall."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(800, 1000)
    host.show()
    popup = ModelPickerPopup((_item("Model", "model"),), parent=host)

    popup.show_attached_to(_top_screen_anchor_rect())
    app.processEvents()

    assert popup._placement_mode is ModelPickerPopupPlacementMode.BELOW
    assert _visible_layout_widgets(popup) == [
        popup._search,
        popup._route_bar,
        popup._view,
    ]
    popup.deleteLater()
    host.deleteLater()


def test_model_picker_popup_above_order_keeps_controls_on_bottom() -> None:
    """Above placement should move search and breadcrumbs below the wall."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 720)
    host.show()
    popup = ModelPickerPopup((_item("Model", "model"),), parent=host)

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


def test_model_picker_popup_above_order_without_embedded_search_places_route_on_bottom() -> (
    None
):
    """Field-driven above placement should place breadcrumbs at the bottom edge."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 720)
    host.show()
    popup = ModelPickerPopup(
        (_item("Model", "model"),),
        show_search_field=False,
        parent=host,
    )

    popup.show_attached_to(_bottom_screen_anchor_rect())
    app.processEvents()

    assert popup._placement_mode is ModelPickerPopupPlacementMode.ABOVE
    assert popup._search.isHidden() is True
    assert _visible_layout_widgets(popup) == [popup._view, popup._route_bar]
    popup.deleteLater()
    host.deleteLater()


def test_model_picker_popup_starved_placement_stays_attached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starved placement should shrink below the anchor instead of detaching."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 400)
    host.show()
    popup = ModelPickerPopup((_item("Model", "model"),), parent=host)
    monkeypatch.setattr(
        model_picker_popup_module,
        "model_picker_screen_available_geometry",
        lambda _anchor_rect: QRect(0, 0, 640, 400),
    )

    popup.show_attached_to(_anchor_rect(100, 190))
    app.processEvents()

    assert popup._placement_mode is ModelPickerPopupPlacementMode.BELOW
    assert popup.geometry().top() == 191
    assert popup.geometry().height() == 400 - 8 - 191
    assert _visible_layout_widgets(popup) == [
        popup._search,
        popup._route_bar,
        popup._view,
    ]
    popup.deleteLater()
    host.deleteLater()


def test_model_picker_popup_can_extend_beyond_owner_widget() -> None:
    """Screen-attached popup geometry should not be constrained to owner size."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(320, 220)
    host.move(_screen_available_geometry().topLeft() + QPoint(24, 24))
    host.show()
    popup = ModelPickerPopup((_item("Model", "model"),), parent=host)

    host_bottom_global = host.mapToGlobal(QPoint(0, host.height())).y()
    popup.show_attached_to(
        QRect(host.mapToGlobal(QPoint(16, host.height() - 24)), QSize(1, 1))
    )
    app.processEvents()

    assert popup.isVisible() is True
    assert popup.geometry().height() > host.height()
    assert popup.geometry().top() + popup.geometry().height() > host_bottom_global
    popup.deleteLater()
    host.deleteLater()


def test_model_picker_popup_hides_on_escape_and_outside_click() -> None:
    """The attached picker should dismiss from keyboard or outside host clicks."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    popup = ModelPickerPopup((_item("Model", "model"),), parent=host)
    popup.show_attached_to(_top_screen_anchor_rect())
    app.processEvents()

    assert popup.isVisible() is True
    QTest.keyClick(popup._search, Qt.Key.Key_Escape)
    app.processEvents()
    assert popup.isVisible() is False

    popup.show_attached_to(_top_screen_anchor_rect(300))
    app.processEvents()
    QTest.mouseClick(host, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
    app.processEvents()

    assert popup.isVisible() is False
    popup.deleteLater()
    host.deleteLater()


def test_model_picker_wall_civitai_action_opens_item_url() -> None:
    """The shared metadata menu action should open model CivitAI URLs."""

    ensure_qapp()
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record opened URLs without launching a browser."""

        opened_urls.append(url)
        return True

    wall = ModelPickerWallView(open_url=open_url)
    target = wall._metadata_context_menu_target(
        _item(
            "Model",
            "model",
            model_page_url="https://civitai.com/models/1?modelVersionId=2",
        )
    )

    assert target is not None
    actions = _actions(wall._metadata_context_menu.menu_items_for_target(target))
    assert len(actions) == 1
    action = actions[0]
    assert action is not None
    action.callback()
    assert opened_urls == ["https://civitai.com/models/1?modelVersionId=2"]
    local_target = wall._metadata_context_menu_target(_item("Local", "local"))
    assert local_target is not None
    assert wall._metadata_context_menu.menu_items_for_target(local_target) == ()


def test_model_picker_wall_refresh_action_targets_item_metadata() -> None:
    """Picker grid refresh actions should target the item's model kind and value."""

    ensure_qapp()
    handler = _MetadataActionHandler()
    wall = ModelPickerWallView(metadata_action_handler=handler)
    target = wall._metadata_context_menu_target(
        _item("Model", "model", model_kind="checkpoints")
    )

    assert target is not None
    actions = _actions(wall._metadata_context_menu.menu_items_for_target(target))

    assert [action.label for action in actions] == [
        "Refresh CivitAI metadata",
        "Set thumbnail from canvas",
    ]
    actions[0].callback()
    assert len(handler.refresh_targets) == 1
    refresh_target = handler.refresh_targets[0]
    assert getattr(refresh_target, "model_kind") == "checkpoints"
    assert getattr(refresh_target, "backend_value") == "Folder/Model.safetensors"


def test_model_picker_wall_items_carry_relative_path_tooltips() -> None:
    """Picker wall items should expose model relative paths as tile tooltips."""

    ensure_qapp()
    popup = ModelPickerPopup(
        (
            _item(
                "Model",
                "model",
            ),
        )
    )

    assert popup._view.items()[0].tooltip == "Folder/Model.safetensors"


def _item(
    title: str,
    search_text: str,
    *,
    folder: str = "Folder",
    payload: object | None = None,
    model_page_url: str | None = None,
    model_kind: str | None = None,
) -> ModelPickerItem:
    """Return one generic model picker item."""

    backend_value = (
        f"{folder}/{title}.safetensors" if folder else f"{title}.safetensors"
    )
    return ModelPickerItem(
        item_id=backend_value,
        title=title,
        subtitle=None,
        backend_value=backend_value,
        relative_path=backend_value,
        folder=folder,
        search_text=search_text,
        thumbnail_variants=(
            ThumbnailVariantReference(
                size=128,
                storage_key=f"{title}:128",
                width=85,
                height=128,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=43520,
            ),
        ),
        aspect_ratio=85 / 128,
        model_page_url=model_page_url,
        payload=title if payload is None else payload,
        model_kind=model_kind,
    )


def _click_route_button(popup: ModelPickerPopup, text: str) -> None:
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


def _visible_layout_widgets(popup: ModelPickerPopup) -> list[QWidget]:
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
