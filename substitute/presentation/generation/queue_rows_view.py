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

"""Render and reorder generation queue rows for queue panel surfaces."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text
from substitute.presentation.localization import LocalizedCaptionLabel

from dataclasses import dataclass
from typing import Any, Literal, cast

try:
    from PySide6.QtCore import Qt, Signal
except ImportError:  # pragma: no cover - lightweight test stubs
    from PySide6.QtCore import Signal

    Qt = object()  # type: ignore[assignment,misc]

try:
    from PySide6.QtGui import QPixmap
except ImportError:  # pragma: no cover - lightweight test stubs
    QPixmap = object  # type: ignore[assignment,misc]

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

try:
    from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight test stubs
    CaptionLabel = QLabel

try:
    from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default queue theme for lightweight test stubs."""

        return True


from substitute.presentation.shell.chrome_style import connect_theme_refresh

try:
    from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect
except ImportError:  # pragma: no cover - lightweight test stubs

    class QApplication:  # type: ignore[no-redef]
        """Fallback QApplication API for lightweight queue row tests."""

        @staticmethod
        def startDragDistance() -> int:
            """Return the standard minimum drag distance."""

            return 10

    QGraphicsDropShadowEffect = None  # type: ignore[assignment,misc]


from substitute.presentation.generation.queue_item_row import (
    GenerationQueueItemRow,
    QueueSurfaceMode,
)
from substitute.presentation.generation.queue_list_view import (
    QueueBucketDividerView,
    QueueDisplayItem,
    QueueJobRowView,
    queue_display_item_rows,
    should_show_pending_resolved_separator,
)
from substitute.presentation.generation.queue_reorder_controller import (
    PendingRowGeometry,
    dispatch_insertion_index_from_visual,
    pending_drop_insertion_index_for_y,
    service_target_index_for_drop,
)


QueueDropSurface = Literal["panel", "flyout"]


@dataclass
class QueueDragState:
    """Track a container-owned pending row drag gesture."""

    job_id: str
    source_visual_index: int
    source_dispatch_index: int
    press_y_offset: int
    press_y: int
    current_y: int
    started: bool = False


class GenerationQueueDropPlaceholder(QFrame):
    """Occupy the pending-row landing slot during a reorder gesture."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the translucent queue drop placeholder."""

        super().__init__(parent)
        self.setObjectName("GenerationQueueDropPlaceholder")
        self.setStyleSheet(
            """
            QFrame#GenerationQueueDropPlaceholder {
                background: rgba(0, 159, 170, 28);
                border: 1px dashed rgba(0, 159, 170, 150);
                border-radius: 6px;
            }
            """
        )

    def set_placeholder_height(self, height: int) -> None:
        """Apply the source row height so the layout opens a matching gap."""

        bounded_height = max(1, height)
        self.setMinimumHeight(bounded_height)
        self.setMaximumHeight(bounded_height)


class GenerationQueueBucketDivider(QWidget):
    """Render an output bucket transition with centered text and framing rules."""

    def __init__(
        self,
        divider: QueueBucketDividerView,
        parent: QWidget | None = None,
    ) -> None:
        """Create a framed bucket-transition divider for adjacent queue groups."""

        super().__init__(parent)
        self.setObjectName("GenerationQueueBucketDivider")
        self._leading_rule = self._create_rule()
        self._trailing_rule = self._create_rule()
        self._label = CaptionLabel(divider.label, self)
        self._label.setObjectName("GenerationQueueBucketDividerLabel")
        _call_if_available(self._label, "setAlignment", cast(Any, Qt).AlignCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 6, 2, 0)
        layout.setSpacing(8)
        layout.addWidget(self._leading_rule, 1)
        layout.addWidget(self._label, 0)
        layout.addWidget(self._trailing_rule, 1)

        self._apply_theme_style()
        connect_theme_refresh(self, self._apply_theme_style)

    def _create_rule(self) -> QFrame:
        """Create one horizontal framing rule for the bucket divider."""

        rule = QFrame(self)
        rule.setObjectName("GenerationQueueBucketDividerRule")
        rule.setFixedHeight(1)
        return rule

    def _apply_theme_style(self) -> None:
        """Refresh rule color for the active QFluent theme."""

        rule_color = "rgba(255, 255, 255, 45)" if isDarkTheme() else "rgba(0, 0, 0, 45)"
        for rule in (self._leading_rule, self._trailing_rule):
            rule.setStyleSheet(
                f"""
                QFrame#GenerationQueueBucketDividerRule {{
                    background: {rule_color};
                    border: none;
                }}
                """
            )


class GenerationQueueDragProxy(QLabel):
    """Show the lifted floating preview for a dragged queue row."""

    def __init__(
        self,
        *,
        pixmap: object | None,
        width: int,
        height: int,
        parent: QWidget | None = None,
    ) -> None:
        """Create a pixmap-backed row drag proxy."""

        super().__init__(parent)
        self.setObjectName("GenerationQueueDragProxy")
        self._apply_theme_style()
        connect_theme_refresh(self, self._apply_theme_style)
        self.setFixedSize(max(1, width), max(1, height))
        self._set_pixmap_if_available(pixmap)
        self._apply_lift_effect()
        _call_if_available(self, "setWindowOpacity", 0.96)
        _call_if_available(self, "setVisible", True)
        _call_if_available(self, "raise_")

    def _apply_theme_style(self) -> None:
        """Refresh the drag proxy surface from the active QFluent theme."""

        if isDarkTheme():
            background = "rgba(35, 39, 43, 235)"
            border = "rgba(255, 255, 255, 36)"
        else:
            background = "rgba(255, 255, 255, 242)"
            border = "rgba(0, 0, 0, 32)"
        self.setStyleSheet(
            f"""
            QLabel#GenerationQueueDragProxy {{
                background: {background};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            """
        )

    def _set_pixmap_if_available(self, pixmap: object | None) -> None:
        """Apply the captured row pixmap when it is usable."""

        if pixmap is None:
            return
        is_null = getattr(pixmap, "isNull", None)
        if callable(is_null) and bool(is_null()):
            return
        set_pixmap = getattr(self, "setPixmap", None)
        if callable(set_pixmap):
            set_pixmap(pixmap)

    def _apply_lift_effect(self) -> None:
        """Add a restrained shadow so the proxy reads as lifted."""

        if QGraphicsDropShadowEffect is None:
            return
        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(18)
        effect.setOffset(0, 8)
        set_color = getattr(effect, "setColor", None)
        if callable(set_color):
            try:
                from PySide6.QtGui import QColor

                set_color(QColor(0, 0, 0, 115))
            except ImportError:
                pass
        set_graphics_effect = getattr(self, "setGraphicsEffect", None)
        if callable(set_graphics_effect):
            set_graphics_effect(effect)


class GenerationQueueRowsView(QWidget):
    """Own queue row layout, reconciliation, and pending-row reorder gestures."""

    cancelRequested = Signal(str)
    removeRequested = Signal(str)
    openSnapshotRequested = Signal(str)
    moveRequested = Signal(str, int)

    def __init__(
        self,
        *,
        surface_mode: QueueSurfaceMode,
        scroll_area: object | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create the shared queue rows container."""

        super().__init__(parent)
        self._surface_mode = surface_mode
        self._scroll_area = scroll_area
        self._rows: tuple[QueueJobRowView, ...] = ()
        self._display_items: tuple[QueueDisplayItem, ...] = ()
        self._row_widgets_by_job_id: dict[str, GenerationQueueItemRow] = {}
        self._drag_state: QueueDragState | None = None
        self._current_insertion_index: int | None = None
        self._drop_placeholder: GenerationQueueDropPlaceholder | None = None
        self._drag_proxy: GenerationQueueDragProxy | None = None
        self.setStyleSheet("background: transparent;")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

    def set_rows(self, rows: tuple[QueueJobRowView, ...]) -> None:
        """Reconcile visible queue rows by job id without recreating survivors."""

        self.set_items(rows)

    def set_items(self, items: tuple[QueueDisplayItem, ...]) -> None:
        """Reconcile visible queue display items by job id."""

        scroll_value = self._scroll_value()
        rows = queue_display_item_rows(items)
        live_job_ids = {row.job_id for row in rows}
        self._remove_stale_widgets(live_job_ids)
        for row in rows:
            self._row_widget_for(row)
        self._rows = rows
        if self._drag_state is not None:
            current_row = next(
                (row for row in rows if row.job_id == self._drag_state.job_id),
                None,
            )
            if (
                current_row is None
                or current_row.interaction_role != "draggable"
                or current_row.pending_visual_index is None
                or current_row.pending_dispatch_index is None
            ):
                self._abort_drag()
        self._display_items = items
        self._rebuild_layout_order(items)
        if self._drag_state is None:
            self._restore_scroll_value(scroll_value)

    def update_row(self, row: QueueJobRowView) -> bool:
        """Update one existing row widget without rebuilding layout order."""

        current_row = self._row_by_job_id(row.job_id)
        row_widget = self._row_widgets_by_job_id.get(row.job_id)
        if current_row is None or row_widget is None:
            return False
        if not _row_placement_matches(current_row, row):
            return False
        self._rows = _replace_row_model(self._rows, row)
        self._display_items = _replace_display_row_model(self._display_items, row)
        row_widget.set_row(row)
        return True

    def _row_widget_for(self, row: QueueJobRowView) -> GenerationQueueItemRow:
        """Return an existing row widget or create and wire a new one."""

        row_widget = self._row_widgets_by_job_id.get(row.job_id)
        if row_widget is not None:
            row_widget.set_row(row)
            return row_widget
        row_widget = GenerationQueueItemRow(
            row,
            self,
            surface_mode=self._surface_mode,
        )
        row_widget.cancelRequested.connect(self.cancelRequested)
        row_widget.removeRequested.connect(self.removeRequested)
        row_widget.openSnapshotRequested.connect(self.openSnapshotRequested)
        row_widget.bodyPressed.connect(self._handle_body_pressed)
        row_widget.bodyMoved.connect(self._handle_body_moved)
        row_widget.bodyReleased.connect(self._handle_body_released)
        self._row_widgets_by_job_id[row.job_id] = row_widget
        return row_widget

    def _remove_stale_widgets(self, live_job_ids: set[str]) -> None:
        """Delete row widgets whose jobs are no longer visible."""

        stale_job_ids = set(self._row_widgets_by_job_id) - live_job_ids
        for job_id in stale_job_ids:
            row_widget = self._row_widgets_by_job_id.pop(job_id)
            row_widget.deleteLater()

    def _rebuild_layout_order(self, items: tuple[QueueDisplayItem, ...]) -> None:
        """Re-add existing display widgets in the requested visual order."""

        self._clear_layout_items(delete_untracked_widgets=True)
        placeholder_inserted = False
        pending_rows_seen = 0
        previous_row: QueueJobRowView | None = None
        for item in items:
            if isinstance(item, QueueBucketDividerView):
                if not placeholder_inserted and pending_rows_seen > 0:
                    placeholder_inserted = self._try_insert_placeholder(
                        pending_rows_seen,
                    )
                self._layout.addWidget(self._create_bucket_divider(item))
                continue
            row = item
            if previous_row is not None and self._should_insert_separator(
                previous_row,
                row,
            ):
                if not placeholder_inserted:
                    placeholder_inserted = self._try_insert_placeholder(
                        pending_rows_seen,
                    )
                self._layout.addWidget(self._create_separator())
            if row.pending_visual_index is not None:
                if not placeholder_inserted:
                    placeholder_inserted = self._try_insert_placeholder(
                        row.pending_visual_index,
                    )
                pending_rows_seen += 1
            elif not placeholder_inserted and pending_rows_seen > 0:
                placeholder_inserted = self._try_insert_placeholder(
                    pending_rows_seen,
                )
            if self._should_skip_drag_source(row):
                previous_row = row
                continue
            self._layout.addWidget(self._row_widgets_by_job_id[row.job_id])
            previous_row = row
        if not placeholder_inserted and pending_rows_seen > 0:
            placeholder_inserted = self._try_insert_placeholder(pending_rows_seen)
        if self._drop_placeholder is not None and not placeholder_inserted:
            self._drop_placeholder.setVisible(False)
        self._layout.addStretch(1)
        _call_if_available(self._layout, "activate")

    def _handle_body_pressed(self, job_id: str, position: object) -> None:
        """Begin tracking a possible pending-row drag from a body press."""

        row = self._row_by_job_id(job_id)
        y_position = _point_y(position)
        widget = self._row_widgets_by_job_id.get(job_id)
        if (
            row is None
            or row.interaction_role != "draggable"
            or row.pending_visual_index is None
            or row.pending_dispatch_index is None
            or y_position is None
            or widget is None
        ):
            return
        self._clear_drag_state()
        self._drag_state = QueueDragState(
            job_id=job_id,
            source_visual_index=row.pending_visual_index,
            source_dispatch_index=row.pending_dispatch_index,
            press_y_offset=y_position - _widget_y(widget),
            press_y=y_position,
            current_y=y_position,
        )
        self._current_insertion_index = row.pending_visual_index
        _call_if_available(widget, "grabMouse")

    def _handle_body_moved(self, job_id: str, position: object) -> None:
        """Update a pending-row drag once movement crosses the drag threshold."""

        if self._drag_state is None or job_id != self._drag_state.job_id:
            return
        y_position = _point_y(position)
        if y_position is None:
            return
        self._drag_state.current_y = y_position
        if not self._drag_state.started:
            if abs(y_position - self._drag_state.press_y) < self._drag_threshold():
                return
            self._start_drag()
        self._update_drag_target(y_position)
        self._move_drag_proxy(y_position)
        self._auto_scroll(y_position)

    def _handle_body_released(self, job_id: str, position: object) -> None:
        """Emit a queue move intent when a pending row is dropped."""

        try:
            if self._drag_state is None or job_id != self._drag_state.job_id:
                return
            y_position = _point_y(position)
            if y_position is not None:
                self._drag_state.current_y = y_position
            if not self._drag_state.started:
                return
            if y_position is not None:
                self._update_drag_target(y_position)
            if self._current_insertion_index is None:
                return
            pending_count = self._pending_count()
            dispatch_insertion_index = dispatch_insertion_index_from_visual(
                self._current_insertion_index,
                pending_count,
            )
            target_index = service_target_index_for_drop(
                source_pending_index=self._drag_state.source_dispatch_index,
                insertion_index=dispatch_insertion_index,
                pending_count=pending_count,
            )
            if target_index is not None:
                self._finish_drag(target_index)
                return
            self._finish_drag(None)
        finally:
            if self._drag_state is not None:
                self._clear_drag_state()

    def _update_drag_target(self, y_position: int) -> None:
        """Update insertion index and placeholder from a container y coordinate."""

        insertion_index = pending_drop_insertion_index_for_y(
            self._pending_row_drag_geometries(),
            y_position,
        )
        if insertion_index == self._current_insertion_index:
            return
        self._current_insertion_index = insertion_index
        self._rebuild_layout_order(self._display_items)

    def _pending_row_drag_geometries(self) -> tuple[PendingRowGeometry, ...]:
        """Build geometry records for visible pending row widgets."""

        geometries: list[PendingRowGeometry] = []
        for row in self._rows:
            if row.pending_visual_index is None:
                continue
            widget = self._row_widgets_by_job_id.get(row.job_id)
            if widget is None:
                continue
            top = _widget_y(widget)
            bottom = top + _widget_height(widget)
            geometries.append(
                PendingRowGeometry(
                    job_id=row.job_id,
                    pending_index=row.pending_visual_index,
                    top=top,
                    bottom=bottom,
                )
            )
        return tuple(geometries)

    def _start_drag(self) -> None:
        """Create placeholder and proxy state once a drag crosses threshold."""

        drag_state = self._drag_state
        if drag_state is None:
            return
        drag_state.started = True
        widget = self._row_widgets_by_job_id.get(drag_state.job_id)
        if widget is None:
            self._abort_drag()
            return
        widget.set_dragging(True)
        widget.set_drag_source_hidden(True)
        self._drop_placeholder = GenerationQueueDropPlaceholder(self)
        self._drop_placeholder.set_placeholder_height(_widget_height(widget))
        self._drag_proxy = GenerationQueueDragProxy(
            pixmap=_grab_widget_pixmap(widget),
            width=_widget_width(widget),
            height=_widget_height(widget),
            parent=self,
        )
        self._rebuild_layout_order(self._display_items)
        self._move_drag_proxy(drag_state.current_y)

    def _finish_drag(self, target_index: int | None) -> None:
        """Commit a real queue move and clear temporary drag visuals immediately."""

        drag_state = self._drag_state
        if drag_state is None:
            return
        job_id = drag_state.job_id
        self._clear_drag_state()
        if target_index is not None:
            self.moveRequested.emit(job_id, target_index)

    def _clear_drag_state(self) -> None:
        """Clear row dragging visuals, drop state, placeholder, and proxy."""

        if self._drag_state is not None:
            widget = self._row_widgets_by_job_id.get(self._drag_state.job_id)
            if widget is not None:
                widget.set_dragging(False)
                widget.set_drag_source_hidden(False)
                _call_if_available(widget, "releaseMouse")
        if self._drop_placeholder is not None:
            self._drop_placeholder.deleteLater()
        if self._drag_proxy is not None:
            self._drag_proxy.deleteLater()
        self._drag_state = None
        self._current_insertion_index = None
        self._drop_placeholder = None
        self._drag_proxy = None
        self._rebuild_layout_order(self._display_items)
        self.update()

    def _abort_drag(self) -> None:
        """Cancel an invalidated drag without emitting a move request."""

        self._clear_drag_state()

    def _pending_count(self) -> int:
        """Return the number of visible pending rows."""

        return sum(1 for row in self._rows if row.pending_visual_index is not None)

    @staticmethod
    def _drag_threshold() -> int:
        """Return the platform drag threshold."""

        start_drag_distance = getattr(QApplication, "startDragDistance", None)
        if callable(start_drag_distance):
            return int(start_drag_distance())
        return 10

    def _height(self) -> int:
        """Return current container height for drag bounds."""

        height_getter = getattr(self, "height", None)
        if callable(height_getter):
            return int(height_getter())
        return 0

    def _row_by_job_id(self, job_id: str) -> QueueJobRowView | None:
        """Return the row model matching a job id."""

        for row in self._rows:
            if row.job_id == job_id:
                return row
        return None

    def _auto_scroll(self, y_position: int) -> None:
        """Scroll the owning queue surface when dragging near visible edges."""

        if self._scroll_area is None:
            return
        scrollbar = self._vertical_scrollbar()
        if scrollbar is None:
            return
        value_getter = getattr(scrollbar, "value", None)
        set_value = getattr(scrollbar, "setValue", None)
        if not callable(value_getter) or not callable(set_value):
            return
        current_value = int(value_getter())
        viewport_height = self._viewport_height()
        viewport_y = y_position - current_value
        scroll_delta = 18
        edge_margin = 32
        target_value = current_value
        if viewport_y < edge_margin:
            target_value -= scroll_delta
        elif viewport_height - viewport_y < edge_margin:
            target_value += scroll_delta
        if target_value == current_value:
            return
        maximum_getter = getattr(scrollbar, "maximum", None)
        maximum = int(maximum_getter()) if callable(maximum_getter) else target_value
        set_value(max(0, min(maximum, target_value)))

    def _scroll_value(self) -> int | None:
        """Return the current vertical scroll value when available."""

        scrollbar = self._vertical_scrollbar()
        if scrollbar is None:
            return None
        value_getter = getattr(scrollbar, "value", None)
        return int(value_getter()) if callable(value_getter) else None

    def _restore_scroll_value(self, value: int | None) -> None:
        """Restore a saved vertical scroll value when available."""

        if value is None:
            return
        scrollbar = self._vertical_scrollbar()
        if scrollbar is None:
            return
        set_value = getattr(scrollbar, "setValue", None)
        if callable(set_value):
            set_value(value)

    def _vertical_scrollbar(self) -> object | None:
        """Return the owner scroll area's vertical scrollbar when available."""

        if self._scroll_area is None:
            return None
        scrollbar_getter = getattr(self._scroll_area, "verticalScrollBar", None)
        if not callable(scrollbar_getter):
            return None
        return cast(object, scrollbar_getter())

    def _viewport_height(self) -> int:
        """Return the visible queue viewport height for auto-scroll."""

        if self._scroll_area is None:
            return self._height()
        viewport_getter = getattr(self._scroll_area, "viewport", None)
        viewport = viewport_getter() if callable(viewport_getter) else self._scroll_area
        height_getter = getattr(viewport, "height", None)
        if callable(height_getter):
            return int(height_getter())
        return self._height()

    def _width(self) -> int:
        """Return current container width."""

        width_getter = getattr(self, "width", None)
        if callable(width_getter):
            return int(width_getter())
        return 0

    def _try_insert_placeholder(self, pending_slot: int) -> bool:
        """Insert the placeholder if it belongs at the supplied pending slot."""

        placeholder = self._drop_placeholder
        if (
            placeholder is None
            or self._current_insertion_index is None
            or pending_slot != self._current_insertion_index
        ):
            return False
        self._layout.addWidget(placeholder)
        placeholder.setVisible(True)
        return True

    def _should_skip_drag_source(self, row: QueueJobRowView) -> bool:
        """Return whether the source row should be replaced by the placeholder."""

        return (
            self._drag_state is not None
            and self._drag_state.started
            and row.job_id == self._drag_state.job_id
        )

    def _move_drag_proxy(self, y_position: int) -> None:
        """Move the floating proxy directly with the pointer."""

        proxy = self._drag_proxy
        drag_state = self._drag_state
        if proxy is None or drag_state is None:
            return
        top = y_position - drag_state.press_y_offset
        move = getattr(proxy, "move", None)
        if callable(move):
            move(0, top)
        else:
            proxy.widget_y = top  # type: ignore[attr-defined]
        _call_if_available(proxy, "raise_")

    def _clear_layout_items(self, *, delete_untracked_widgets: bool) -> None:
        """Remove all layout items, deleting only non-row widgets when requested."""

        tracked_widgets: set[QWidget] = set(self._row_widgets_by_job_id.values())
        if self._drop_placeholder is not None:
            tracked_widgets.add(self._drop_placeholder)
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget_getter = getattr(item, "widget", None)
            widget = widget_getter() if callable(widget_getter) else None
            if (
                delete_untracked_widgets
                and widget is not None
                and widget not in tracked_widgets
            ):
                widget.deleteLater()

    def _clear_rows(self) -> None:
        """Remove all current row widgets and layout-only widgets."""

        self._clear_layout_items(delete_untracked_widgets=True)
        for row_widget in self._row_widgets_by_job_id.values():
            row_widget.deleteLater()
        self._row_widgets_by_job_id = {}
        self._rows = ()
        self._display_items = ()
        self._clear_drag_state()

    def _should_insert_separator(
        self,
        previous_row: QueueJobRowView,
        row: QueueJobRowView,
    ) -> bool:
        """Return whether a resolved separator belongs between two rows."""

        return (
            should_show_pending_resolved_separator(self._rows)
            and previous_row.visual_role == "pending"
            and row.visual_role == "resolved"
        )

    def _create_separator(self) -> QLabel:
        """Create the quiet pending/resolved separator label."""

        separator = LocalizedCaptionLabel(app_text("Resolved"), self)
        separator.setObjectName("GenerationQueueResolvedSeparator")
        separator.setContentsMargins(2, 4, 2, 0)
        return cast(QLabel, separator)

    def _create_bucket_divider(self, divider: QueueBucketDividerView) -> QWidget:
        """Create the framed output bucket transition divider."""

        return GenerationQueueBucketDivider(divider, self)


def _row_placement_matches(
    current: QueueJobRowView,
    candidate: QueueJobRowView,
) -> bool:
    """Return whether a row can be updated without layout reconciliation."""

    return (
        current.job_id == candidate.job_id
        and current.visual_role == candidate.visual_role
        and current.interaction_role == candidate.interaction_role
        and current.pending_visual_index == candidate.pending_visual_index
        and current.pending_dispatch_index == candidate.pending_dispatch_index
        and current.bucket_key == candidate.bucket_key
        and current.bucket_label == candidate.bucket_label
    )


def _replace_row_model(
    rows: tuple[QueueJobRowView, ...],
    replacement: QueueJobRowView,
) -> tuple[QueueJobRowView, ...]:
    """Return row models with one job row replaced."""

    return tuple(
        replacement if row.job_id == replacement.job_id else row for row in rows
    )


def _replace_display_row_model(
    items: tuple[QueueDisplayItem, ...],
    replacement: QueueJobRowView,
) -> tuple[QueueDisplayItem, ...]:
    """Return display models with one job row replaced."""

    return tuple(
        replacement
        if isinstance(item, QueueJobRowView) and item.job_id == replacement.job_id
        else item
        for item in items
    )


def _point_y(point: object) -> int | None:
    """Return the y coordinate of a QPoint-like object."""

    y_getter = getattr(point, "y", None)
    if callable(y_getter):
        return int(y_getter())
    return None


def _widget_y(widget: QWidget) -> int:
    """Return a widget y position for drag calculations."""

    y_getter = getattr(widget, "y", None)
    return int(y_getter()) if callable(y_getter) else 0


def _widget_height(widget: QWidget) -> int:
    """Return a widget height for drag calculations."""

    height_getter = getattr(widget, "height", None)
    return int(height_getter()) if callable(height_getter) else 0


def _widget_width(widget: QWidget) -> int:
    """Return a widget width for drag proxy sizing."""

    width_getter = getattr(widget, "width", None)
    return int(width_getter()) if callable(width_getter) else 0


def _is_widget_visible(widget: QWidget) -> bool:
    """Return whether a QWidget-like object is visible."""

    visible_getter = getattr(widget, "isVisible", None)
    if callable(visible_getter):
        return bool(visible_getter())
    return bool(getattr(widget, "visible", True))


def _grab_widget_pixmap(widget: QWidget) -> QPixmap | None:
    """Capture one row pixmap when the widget implementation supports it."""

    grab = getattr(widget, "grab", None)
    if not callable(grab):
        return None
    return cast(QPixmap, grab())


def _call_if_available(target: object, name: str, *args: object) -> object | None:
    """Call a named method when it exists on a Qt or test-stub object."""

    method = getattr(target, name, None)
    if not callable(method):
        return None
    return cast(object, method(*args))


__all__ = [
    "GenerationQueueDragProxy",
    "GenerationQueueBucketDivider",
    "GenerationQueueDropPlaceholder",
    "GenerationQueueRowsView",
    "PendingRowGeometry",
    "QueueDragState",
    "dispatch_insertion_index_from_visual",
    "pending_drop_insertion_index_for_y",
    "service_target_index_for_drop",
]
