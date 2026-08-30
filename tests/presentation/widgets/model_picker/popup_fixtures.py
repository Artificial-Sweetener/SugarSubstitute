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

"""Provide deterministic values and mounted helpers for popup tests."""

from __future__ import annotations

from typing import cast
from uuid import UUID


from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.domain.model_metadata import ThumbnailAsset
from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
)
from substitute.presentation.widgets.media_wall import ThumbnailVariantReference
from substitute.presentation.widgets.model_picker import (
    ModelPickerItem,
    ModelPickerPopup,
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
