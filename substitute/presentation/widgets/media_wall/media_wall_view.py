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

"""Provide a reusable Qt justified media wall view."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Callable
from dataclasses import dataclass
import time
from typing import cast

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QCursor,
    QKeyEvent,
    QMouseEvent,
    QPaintEvent,
    QResizeEvent,
    QShowEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QAbstractScrollArea, QWidget
from qfluentwidgets import ScrollBar  # type: ignore[import-untyped]

from substitute.application.execution import TaskSubmitter
from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.presentation.widgets.cursor_tooltip_filter import (
    CursorToolTipFilter,
    install_cursor_tooltip_filter,
)
from substitute.presentation.widgets.media_wall.justified_layout import (
    JustifiedLayoutInput,
    JustifiedLayoutItem,
    PickerJustifiedWallProfile,
    build_justified_rows,
)
from substitute.presentation.widgets.media_wall.media_wall_item import MediaWallItem
from substitute.presentation.widgets.media_wall.media_wall_marquee import (
    TitleMarqueeState,
    resolve_title_marquee_state,
)
from substitute.presentation.widgets.media_wall.media_wall_painter import (
    paint_media_wall_tile,
    title_and_subtitle_rects,
)
from substitute.presentation.widgets.media_wall.media_wall_thumbnail_cache import (
    MediaWallThumbnailCache,
)
from substitute.presentation.widgets.media_wall.media_wall_thumbnail_preloader import (
    MediaWallThumbnailPreloader,
)
from substitute.presentation.widgets.picker_keyboard_navigation import (
    PickerKeyboardAction,
    picker_keyboard_action_from_event,
)


@dataclass(frozen=True, slots=True)
class _PlacedMediaWallItem:
    """Store one viewport-independent tile geometry."""

    item: MediaWallItem
    rect: QRect


@dataclass(frozen=True, slots=True)
class _PlacedMediaWallRow:
    """Store row bounds and the placed item indexes in that visual row."""

    top: int
    bottom: int
    item_indexes: tuple[int, ...]


class MediaWallView(QAbstractScrollArea):
    """Render a justified wall without creating one QWidget per tile."""

    itemActivated = Signal(object)
    itemContextMenuRequested = Signal(object, QPoint)
    _DEFAULT_WHEEL_STEP = 72
    _OVERSCAN_ROWS = 1

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        asset_repository: ThumbnailAssetRepository | None = None,
        thumbnail_cache: MediaWallThumbnailCache | None = None,
        thumbnail_preloader: MediaWallThumbnailPreloader | None = None,
        thumbnail_submitter: TaskSubmitter | None = None,
        close_thumbnail_submitter: Callable[[], None] | None = None,
        profile: PickerJustifiedWallProfile | None = None,
    ) -> None:
        """Initialize a scrollable media wall view."""

        super().__init__(parent)
        self._items: tuple[MediaWallItem, ...] = ()
        self._placed_items: tuple[_PlacedMediaWallItem, ...] = ()
        self._placed_rows: tuple[_PlacedMediaWallRow, ...] = ()
        self._row_tops: tuple[int, ...] = ()
        self._row_bottoms: tuple[int, ...] = ()
        self._row_index_by_item_index: dict[int, int] = {}
        self._item_index_by_id: dict[str, int] = {}
        self._placed_item_by_id: dict[str, _PlacedMediaWallItem] = {}
        self._hovered_item_id: str | None = None
        self._current_index = -1
        self._profile = profile or PickerJustifiedWallProfile()
        self._thumbnail_cache = thumbnail_cache or MediaWallThumbnailCache(
            asset_repository=asset_repository
        )
        self._owns_thumbnail_preloader = (
            thumbnail_preloader is None and asset_repository is not None
        )
        self._thumbnail_preloader = thumbnail_preloader
        if (
            self._thumbnail_preloader is None
            and asset_repository is not None
            and thumbnail_submitter is not None
        ):
            self._thumbnail_preloader = MediaWallThumbnailPreloader(
                cache=self._thumbnail_cache,
                asset_repository=asset_repository,
                submitter=thumbnail_submitter,
                close_submitter=close_thumbnail_submitter,
                parent=self,
            )
        if self._thumbnail_preloader is not None:
            self._thumbnail_preloader.thumbnailReady.connect(
                self._handle_thumbnail_ready
            )
        self._title_marquee_started_ms = _monotonic_ms()
        self._title_marquee_timer = QTimer(self)
        self._title_marquee_timer.setInterval(33)
        self._title_marquee_timer.timeout.connect(self.viewport().update)
        self._tooltip_filter: CursorToolTipFilter | None = None
        self.setFrameShape(QAbstractScrollArea.Shape.NoFrame)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.verticalScrollBar().valueChanged.connect(self._handle_scroll_changed)
        self._fluent_vertical_scroll_bar = ScrollBar(Qt.Orientation.Vertical, self)
        self._install_tooltip_filter()

    def set_items(self, items: tuple[MediaWallItem, ...]) -> None:
        """Replace the items rendered by the wall."""

        self.verticalScrollBar()
        self._items = items
        self._hovered_item_id = None
        self._current_index = 0 if items else -1
        self._reset_title_marquee()
        self._rebuild_layout()
        self._sync_title_marquee_timer()
        self._request_visible_thumbnail_preloads()
        self.viewport().update()

    def items(self) -> tuple[MediaWallItem, ...]:
        """Return the current wall items."""

        return self._items

    def current_index(self) -> int:
        """Return the current keyboard-selection index."""

        return self._current_index

    def set_current_index(self, index: int) -> None:
        """Select one item by index, clearing selection when it is invalid."""

        self.verticalScrollBar()
        if index < 0 or index >= len(self._items):
            self._current_index = -1
            self._reset_title_marquee()
            self._sync_title_marquee_timer()
            self.viewport().update()
            return
        self._current_index = index
        self._reset_title_marquee()
        self._sync_title_marquee_timer()
        self._ensure_current_visible()
        self.viewport().update()

    def move_current(self, delta: int) -> None:
        """Move the current selection by a relative item count."""

        self._move_current(delta)

    def move_current_left(self) -> None:
        """Move selection one item left in row-major order."""

        self._move_current(-1)

    def move_current_right(self) -> None:
        """Move selection one item right in row-major order."""

        self._move_current(1)

    def move_current_up(self) -> None:
        """Move selection to the nearest item in the previous visual row."""

        self._move_current_vertical(-1)

    def move_current_down(self) -> None:
        """Move selection to the nearest item in the next visual row."""

        self._move_current_vertical(1)

    def activate_current(self) -> bool:
        """Emit activation for the current item when one is selected."""

        item = self._current_item()
        if item is None:
            return False
        self.itemActivated.emit(item.payload)
        return True

    def current_payload(self) -> object | None:
        """Return the payload for the current item when one is selected."""

        item = self._current_item()
        return None if item is None else item.payload

    def tooltip_text_at(self, point: QPoint) -> str | None:
        """Return tooltip text for the tile at one viewport-local point."""

        item = self._item_at(point)
        if item is None:
            return None
        return item.tooltip

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint visible wall tiles."""

        from PySide6.QtGui import QPainter

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(event.rect(), self.palette().base())
        scroll_offset = self.verticalScrollBar().value()
        visible_rect = event.rect()
        visible_document_rect = visible_rect.translated(0, scroll_offset)
        current_item_id = self._current_item_id()
        for row_index in self._visible_row_indexes(visible_document_rect):
            for item_index in self._placed_rows[row_index].item_indexes:
                placed = self._placed_items[item_index]
                viewport_rect = placed.rect.translated(0, -scroll_offset)
                paint_media_wall_tile(
                    painter,
                    self,
                    item=placed.item,
                    rect=viewport_rect,
                    hovered=placed.item.item_id == self._hovered_item_id,
                    current=placed.item.item_id == current_item_id,
                    thumbnail_cache=self._thumbnail_cache,
                    title_marquee_state=self._title_marquee_state_for_item(
                        placed.item,
                        viewport_rect,
                    ),
                )

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Relayout the wall when viewport width changes."""

        super().resizeEvent(event)
        self._rebuild_layout()
        self._reset_title_marquee()
        self._sync_title_marquee_timer()
        self._request_visible_thumbnail_preloads()

    def showEvent(self, event: QShowEvent) -> None:
        """Queue first visible thumbnail preloads after the wall is shown."""

        super().showEvent(event)
        self._request_visible_thumbnail_preloads()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop internally owned thumbnail preload tasks when the wall closes."""

        if self._owns_thumbnail_preloader and self._thumbnail_preloader is not None:
            self._thumbnail_preloader.shutdown()
        super().closeEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Track the hovered tile without triggering relayout."""

        hovered = self._item_at(event.position().toPoint())
        next_hovered_item_id = None if hovered is None else hovered.item_id
        if next_hovered_item_id != self._hovered_item_id:
            self._hovered_item_id = next_hovered_item_id
            self._reset_title_marquee()
            self._sync_title_marquee_timer()
            self.viewport().update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hover when the pointer leaves the wall viewport."""

        if self._hovered_item_id is not None:
            self._hovered_item_id = None
            self._reset_title_marquee()
            self._sync_title_marquee_timer()
            self.viewport().update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Activate or request a context menu for the clicked item."""

        if event.button() not in {
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.RightButton,
        }:
            super().mousePressEvent(event)
            return
        item = self._item_at(event.position().toPoint())
        if item is None:
            super().mousePressEvent(event)
            return
        self._set_current_item(item.item_id)
        if event.button() == Qt.MouseButton.RightButton:
            self.itemContextMenuRequested.emit(
                item.payload,
                event.globalPosition().toPoint(),
            )
        else:
            self.itemActivated.emit(item.payload)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Support basic keyboard navigation and activation."""

        action = picker_keyboard_action_from_event(event)
        if action is PickerKeyboardAction.ACTIVATE:
            if self.activate_current():
                event.accept()
                return
        if action is PickerKeyboardAction.RIGHT:
            self.move_current_right()
            event.accept()
            return
        if action is PickerKeyboardAction.LEFT:
            self.move_current_left()
            event.accept()
            return
        if action is PickerKeyboardAction.DOWN:
            self.move_current_down()
            event.accept()
            return
        if action is PickerKeyboardAction.UP:
            self.move_current_up()
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Scroll the pixel-based wall at a row-appropriate speed."""

        scroll_bar = self.verticalScrollBar()
        pixel_delta = event.pixelDelta().y()
        if pixel_delta:
            scroll_bar.setValue(scroll_bar.value() - pixel_delta)
            event.accept()
            return
        angle_delta = event.angleDelta().y()
        if angle_delta == 0:
            super().wheelEvent(event)
            return
        notches = angle_delta / 120.0
        scroll_bar.setValue(
            scroll_bar.value() - round(notches * self._wheel_step_pixels())
        )
        event.accept()

    def _rebuild_layout(self) -> None:
        """Solve row geometry and update the scroll range."""

        scroll_bar = self.verticalScrollBar()
        width = max(1, self.viewport().width())
        rows = build_justified_rows(
            JustifiedLayoutInput(
                items=tuple(
                    JustifiedLayoutItem(
                        aspect_ratio=item.aspect_ratio,
                        payload=item,
                    )
                    for item in self._items
                ),
                container_width=width,
                target_row_height=self._profile.target_row_height,
                min_row_height=self._profile.min_row_height,
                max_row_height=self._profile.max_row_height,
                gutter=self._profile.gutter,
                minimum_tile_width=self._profile.minimum_tile_width,
            )
        )
        placed_items: list[_PlacedMediaWallItem] = []
        placed_rows: list[_PlacedMediaWallRow] = []
        row_index_by_item_index: dict[int, int] = {}
        item_index_by_id: dict[str, int] = {}
        placed_item_by_id: dict[str, _PlacedMediaWallItem] = {}
        y = 0
        for row_index, row in enumerate(rows):
            x = 0
            row_height = max(1, round(row.height))
            row_start = len(placed_items)
            for row_item in row.items:
                item_width = max(1, round(row_item.width))
                item_index = len(placed_items)
                placed = _PlacedMediaWallItem(
                    item=row_item.payload,
                    rect=QRect(x, y, item_width, row_height),
                )
                placed_items.append(placed)
                row_index_by_item_index[item_index] = row_index
                item_index_by_id.setdefault(row_item.payload.item_id, item_index)
                placed_item_by_id.setdefault(row_item.payload.item_id, placed)
                x += item_width + round(self._profile.gutter)
            if len(placed_items) > row_start:
                placed_rows.append(
                    _PlacedMediaWallRow(
                        top=y,
                        bottom=y + row_height - 1,
                        item_indexes=tuple(range(row_start, len(placed_items))),
                    )
                )
            y += row_height + round(self._profile.gutter)
        total_height = max(0, y - round(self._profile.gutter))
        self._placed_items = tuple(placed_items)
        self._placed_rows = tuple(placed_rows)
        self._row_tops = tuple(row.top for row in self._placed_rows)
        self._row_bottoms = tuple(row.bottom for row in self._placed_rows)
        self._row_index_by_item_index = row_index_by_item_index
        self._item_index_by_id = item_index_by_id
        self._placed_item_by_id = placed_item_by_id
        scroll_bar.setPageStep(self.viewport().height())
        scroll_bar.setSingleStep(self._wheel_step_pixels())
        scroll_bar.setRange(0, max(0, total_height - self.viewport().height()))
        self._sync_fluent_scroll_bar_steps()

    def _install_tooltip_filter(self) -> None:
        """Install QFluent cursor tooltips for dynamic tile hover text."""

        self._tooltip_filter = install_cursor_tooltip_filter(
            self,
            self.viewport(),
            show_delay_ms=600,
            tooltip_provider=self._tooltip_for_hover_event,
        )

    def _tooltip_for_hover_event(self, watched: object, event: object) -> str | None:
        """Return the tooltip for the item under the current hover event."""

        _ = watched
        point = _local_event_point(event)
        if point is None:
            point = self.viewport().mapFromGlobal(QCursor.pos())
        return self.tooltip_text_at(point)

    def _sync_fluent_scroll_bar_steps(self) -> None:
        """Keep QFluent scroll chrome aligned with the partner scrollbar steps."""

        scroll_bar = self.verticalScrollBar()
        self._fluent_vertical_scroll_bar.setPageStep(scroll_bar.pageStep())
        self._fluent_vertical_scroll_bar.setSingleStep(scroll_bar.singleStep())

    def _handle_scroll_changed(self) -> None:
        """Refresh visible thumbnails and repaint after scroll position changes."""

        self._request_visible_thumbnail_preloads()
        self.viewport().update()

    def _handle_thumbnail_ready(self, storage_key: str) -> None:
        """Repaint when an async thumbnail publication reaches the cache."""

        _ = storage_key
        self.viewport().update()

    def _request_visible_thumbnail_preloads(self) -> None:
        """Queue async thumbnail preloads for visible and overscan wall rows."""

        preloader = self._thumbnail_preloader
        if preloader is None or not self._placed_rows or not self.isVisible():
            return
        scroll_offset = self.verticalScrollBar().value()
        visible_document_rect = self.viewport().rect().translated(0, scroll_offset)
        device_pixel_ratio = self.devicePixelRatioF()
        for row_index in self._visible_row_indexes(visible_document_rect):
            for item_index in self._placed_rows[row_index].item_indexes:
                placed = self._placed_items[item_index]
                preloader.preload_pixmap_for_variants(
                    placed.item.thumbnail_variants,
                    placed.rect.size(),
                    device_pixel_ratio=device_pixel_ratio,
                )

    def _item_at(self, point: QPoint) -> MediaWallItem | None:
        """Return the media wall item at one viewport-local point."""

        document_point = QPoint(point.x(), point.y() + self.verticalScrollBar().value())
        row = self._row_at_document_y(document_point.y())
        if row is None:
            return None
        for item_index in reversed(row.item_indexes):
            placed = self._placed_items[item_index]
            if placed.rect.contains(document_point):
                return placed.item
        return None

    def _set_current_item(self, item_id: str) -> None:
        """Select one item as the keyboard-current item."""

        index = self._item_index_by_id.get(item_id)
        if index is None:
            return
        self._current_index = index
        self._reset_title_marquee()
        self._sync_title_marquee_timer()
        self.viewport().update()

    def _current_item_id(self) -> str | None:
        """Return the currently selected item id."""

        item = self._current_item()
        return None if item is None else item.item_id

    def _current_item(self) -> MediaWallItem | None:
        """Return the currently selected item."""

        if self._current_index < 0 or self._current_index >= len(self._items):
            return None
        return self._items[self._current_index]

    def _move_current(self, delta: int) -> None:
        """Move current selection by one item and keep it visible."""

        if not self._items:
            return
        self._current_index = max(
            0,
            min(len(self._items) - 1, self._current_index + delta),
        )
        self._reset_title_marquee()
        self._sync_title_marquee_timer()
        self._ensure_current_visible()
        self.viewport().update()

    def _move_current_vertical(self, row_delta: int) -> None:
        """Move current selection vertically by visual rows, wrapping top/bottom."""

        if not self._items:
            return
        if not self._placed_rows:
            self._move_current(row_delta)
            return
        current_index = self._current_index
        if current_index < 0 or current_index >= len(self._placed_items):
            self.set_current_index(0 if row_delta > 0 else len(self._items) - 1)
            return
        current_row_index = self._row_index_by_item_index.get(current_index)
        if current_row_index is None:
            return

        target_row_index = current_row_index + row_delta
        if target_row_index < 0:
            target_row_index = len(self._placed_rows) - 1
        elif target_row_index >= len(self._placed_rows):
            target_row_index = 0

        current_center_x = self._placed_items[current_index].rect.center().x()
        target_index = min(
            self._placed_rows[target_row_index].item_indexes,
            key=lambda index: abs(
                self._placed_items[index].rect.center().x() - current_center_x
            ),
        )
        self.set_current_index(target_index)

    def _ensure_current_visible(self) -> None:
        """Scroll enough to keep the current tile visible."""

        placed = self._placed_item_for_index(self._current_index)
        if placed is None:
            return
        scroll_bar = self.verticalScrollBar()
        top = placed.rect.top()
        bottom = placed.rect.bottom()
        visible_top = scroll_bar.value()
        visible_bottom = visible_top + self.viewport().height()
        target_value = visible_top
        if top < visible_top:
            target_value = top
            scroll_bar.setValue(target_value)
        elif bottom > visible_bottom:
            target_value = bottom - self.viewport().height()
            scroll_bar.setValue(target_value)

    def _placed_item_for_index(self, index: int) -> _PlacedMediaWallItem | None:
        """Return placed geometry for one item index when layout has it."""

        if index < 0 or index >= len(self._placed_items):
            return None
        return self._placed_items[index]

    def _visible_row_indexes(self, document_rect: QRect) -> range:
        """Return row indexes intersecting the document rect plus overscan."""

        if not self._placed_rows:
            return range(0)
        first = bisect_left(self._row_bottoms, document_rect.top())
        last = bisect_right(self._row_tops, document_rect.bottom()) - 1
        if first > last:
            return range(0)
        start = max(0, first - self._OVERSCAN_ROWS)
        stop = min(len(self._placed_rows), last + self._OVERSCAN_ROWS + 1)
        return range(start, stop)

    def _row_at_document_y(self, y: int) -> _PlacedMediaWallRow | None:
        """Return the visual row containing a document-space y coordinate."""

        row_index = bisect_right(self._row_tops, y) - 1
        if row_index < 0 or row_index >= len(self._placed_rows):
            return None
        row = self._placed_rows[row_index]
        if y > row.bottom:
            return None
        return row

    def _wheel_step_pixels(self) -> int:
        """Return the per-notch scroll distance for mouse-wheel events."""

        profile_step = round(self._profile.target_row_height * 0.55)
        return max(48, profile_step, self._DEFAULT_WHEEL_STEP)

    def _title_marquee_state_for_item(
        self,
        item: MediaWallItem,
        viewport_rect: QRect,
    ) -> TitleMarqueeState | None:
        """Return title marquee state for the active item when title text overflows."""

        active_item_id = self._active_title_item_id()
        if item.item_id != active_item_id:
            return None
        title_rect, _subtitle_rect = title_and_subtitle_rects(
            viewport_rect,
            self.fontMetrics(),
            subtitle_visible=bool(item.subtitle),
        )
        overflow_width = self.fontMetrics().horizontalAdvance(item.title) - (
            title_rect.width()
        )
        if overflow_width <= 0:
            return None
        return resolve_title_marquee_state(
            elapsed_ms=_monotonic_ms() - self._title_marquee_started_ms,
            overflow_width=overflow_width,
        )

    def _active_title_item_id(self) -> str | None:
        """Return the item id whose title should be eligible for marquee."""

        if self._hovered_item_id is not None:
            return self._hovered_item_id
        return self._current_item_id()

    def _sync_title_marquee_timer(self) -> None:
        """Run the title marquee timer only while the active title overflows."""

        if self._active_title_overflow_width() > 0:
            if not self._title_marquee_timer.isActive():
                self._title_marquee_timer.start()
            return
        self._title_marquee_timer.stop()

    def _active_title_overflow_width(self) -> int:
        """Return active title overflow in pixels, or zero when no marquee is needed."""

        active_item_id = self._active_title_item_id()
        if active_item_id is None:
            return 0
        placed = self._placed_item_by_id.get(active_item_id)
        if placed is None:
            return 0
        title_rect, _subtitle_rect = title_and_subtitle_rects(
            placed.rect,
            self.fontMetrics(),
            subtitle_visible=bool(placed.item.subtitle),
        )
        return max(
            0,
            self.fontMetrics().horizontalAdvance(placed.item.title)
            - title_rect.width(),
        )

    def _reset_title_marquee(self) -> None:
        """Restart title marquee timing from the readable start hold."""

        self._title_marquee_started_ms = _monotonic_ms()


def _monotonic_ms() -> int:
    """Return monotonic time in milliseconds for UI animation timing."""

    return round(time.monotonic() * 1000.0)


def _local_event_point(event: object) -> QPoint | None:
    """Return a local event point across Qt mouse, hover, and tooltip events."""

    position = getattr(event, "position", None)
    if callable(position):
        to_point = getattr(position(), "toPoint", None)
        if callable(to_point):
            return cast(QPoint, to_point())
    pos = getattr(event, "pos", None)
    if callable(pos):
        candidate = pos()
        if isinstance(candidate, QPoint):
            return candidate
    return None


__all__ = ["MediaWallView"]
