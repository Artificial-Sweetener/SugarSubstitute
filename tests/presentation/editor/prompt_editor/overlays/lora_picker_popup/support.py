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

"""Deterministic fixtures and Qt helpers for LoRA picker popup contracts."""

from __future__ import annotations


from typing import cast
from uuid import UUID

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
    PromptLoraThumbnailVariant,
)
from substitute.domain.model_metadata import (
    STANDARD_THUMBNAIL_ROLE,
    ThumbnailAsset,
)
from substitute.presentation.editor.prompt_editor.overlays import PromptLoraPickerPopup
from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
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
