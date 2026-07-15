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

"""Render one generation queue row with a per-job cancel action."""

from __future__ import annotations

from typing import Any, Literal, cast

try:
    from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, Signal
except ImportError:  # pragma: no cover - lightweight test stubs
    from PySide6.QtCore import Qt, Signal

    class QEvent:  # type: ignore[no-redef]
        """Fallback QEvent enum container for lightweight queue row tests."""

        class Type:
            """Fallback event type names."""

            MouseButtonPress = "mouse-press"
            MouseMove = "mouse-move"
            MouseButtonRelease = "mouse-release"

    class QPoint:  # type: ignore[no-redef]
        """Fallback QPoint for lightweight queue row tests."""

        def __init__(self, x: int = 0, y: int = 0) -> None:
            """Store x and y values."""

            self._x = x
            self._y = y

        def __sub__(self, other: "QPoint") -> "QPoint":
            """Return coordinate delta."""

            this = cast(Any, self)
            that = cast(Any, other)
            return QPoint(this._x - that._x, this._y - that._y)

        def manhattanLength(self) -> int:
            """Return a Manhattan distance approximation."""

            return abs(self._x) + abs(self._y)

    class QRect:  # type: ignore[no-redef]
        """Fallback QRect for lightweight queue row tests."""

    class QRectF:  # type: ignore[no-redef]
        """Fallback QRectF for lightweight queue row tests."""

        def __init__(self, _rect: object) -> None:
            """Accept a source rectangle."""

    class QSize:  # type: ignore[no-redef]
        """Fallback QSize for lightweight queue row tests."""

        def __init__(self, width: int, height: int) -> None:
            """Store width and height."""

            self._width = width
            self._height = height

        def width(self) -> int:
            """Return stored width."""

            return self._width

        def height(self) -> int:
            """Return stored height."""

            return self._height


try:
    from PySide6.QtGui import QFontMetrics, QPainter, QPainterPath, QPaintEvent
except ImportError:  # pragma: no cover - lightweight test stubs
    QPaintEvent = object  # type: ignore[misc,assignment]
    QPainter = None  # type: ignore[misc,assignment]

    class QPainterPath:  # type: ignore[no-redef]
        """Fallback path for lightweight queue row tests."""

        def addRoundedRect(
            self,
            _rect: object,
            _x_radius: float,
            _y_radius: float,
        ) -> None:
            """Accept rounded-rect path commands."""

    class QFontMetrics:  # type: ignore[no-redef]
        """Fallback font metrics for lightweight queue row tests."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            """Create deterministic test metrics."""

        def elidedText(
            self,
            text: str,
            _mode: object,
            width: int,
        ) -> str:
            """Return deterministic right-elided text for lightweight tests."""

            if width <= 0:
                return ""
            character_budget = max(1, width // 7)
            if len(text) <= character_budget:
                return text
            if character_budget <= 3:
                return "." * character_budget
            return f"{text[: character_budget - 3].rstrip()}..."

        def tightBoundingRect(self, _text: str) -> object:
            """Return a small rectangle-like text bound."""

            return type("_Rect", (), {"height": lambda self: 10})()


from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]
from qfluentwidgets import TransparentToolButton
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]

try:
    from qfluentwidgets import CaptionLabel, StrongBodyLabel
except ImportError:  # pragma: no cover - lightweight test stubs
    CaptionLabel = QLabel
    StrongBodyLabel = QLabel


from substitute.presentation.generation.queue_thumbnail_cache import (
    GenerationQueueThumbnailCache,
)
from substitute.presentation.generation.queue_list_view import QueueJobRowView
from substitute.presentation.widgets.row_interaction_feedback import (
    RowInteractionFeedback,
    is_left_mouse_press,
)
from substitute.presentation.widgets.cursor_tooltip_filter import (
    install_cursor_tooltip_filter,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh


_THUMBNAIL_CACHE = GenerationQueueThumbnailCache()
_THUMBNAIL_SIZE = QSize(52, 52)
_QUEUE_TITLE_FONT_DELTA = 1
_QUEUE_SUBTITLE_FONT_DELTA = -1
_QUEUE_MINIMUM_TITLE_POINT_SIZE = 9
_QUEUE_MINIMUM_SUBTITLE_POINT_SIZE = 8
QueueSurfaceMode = Literal["panel", "flyout"]


def _queue_thumbnail_stylesheet() -> str:
    """Return the thumbnail placeholder stylesheet for the active QFluent theme."""

    if isDarkTheme():
        background = "rgba(255, 255, 255, 16)"
        border = "rgba(255, 255, 255, 20)"
    else:
        background = "rgba(0, 0, 0, 8)"
        border = "rgba(0, 0, 0, 18)"
    return f"""
            QLabel#GenerationQueueItemThumbnail {{
                background: {background};
                border: 1px solid {border};
                border-radius: 5px;
            }}
            """


def _queue_row_surface_colors(row: QueueJobRowView) -> tuple[str, str]:
    """Return row background and border colors for the active QFluent theme."""

    if isDarkTheme():
        base_background = "rgba(255, 255, 255, 18)"
        border = (
            "rgba(255, 255, 255, 28)"
            if row.visual_role == "active"
            else ("rgba(255, 255, 255, 22)")
        )
        return base_background, border
    base_background = "rgba(255, 255, 255, 225)"
    border = (
        "rgba(0, 0, 0, 32)" if row.visual_role == "active" else ("rgba(0, 0, 0, 20)")
    )
    return base_background, border


def _set_label_point_size_delta(label: QLabel, *, delta: int, minimum: int) -> None:
    """Apply a bounded point-size delta when the active Qt binding exposes fonts."""

    font_getter = getattr(label, "font", None)
    set_font = getattr(label, "setFont", None)
    if not callable(font_getter) or not callable(set_font):
        return

    font = cast(Any, font_getter())
    point_size_getter = getattr(font, "pointSize", None)
    set_point_size = getattr(font, "setPointSize", None)
    if not callable(point_size_getter) or not callable(set_point_size):
        return

    point_size = int(point_size_getter())
    if point_size <= 0:
        return
    set_point_size(max(minimum, point_size + delta))
    set_font(font)


def _tight_label_height(label: QLabel) -> int:
    """Return a compact label height derived from the current label font."""

    font_getter = getattr(label, "font", None)
    if not callable(font_getter):
        return 14
    metrics = QFontMetrics(cast(Any, font_getter()))
    bounds = metrics.tightBoundingRect("Ag")
    height_getter = getattr(bounds, "height", None)
    if not callable(height_getter):
        return 14
    return max(1, int(height_getter()) + 4)


def _allow_horizontal_shrink(widget: QWidget) -> None:
    """Allow a label-like widget to shrink before forcing parent width."""

    set_minimum_width = getattr(widget, "setMinimumWidth", None)
    if callable(set_minimum_width):
        set_minimum_width(0)
    set_size_policy = getattr(widget, "setSizePolicy", None)
    if not callable(set_size_policy):
        return
    try:
        from PySide6.QtWidgets import QSizePolicy
    except ImportError:
        return
    set_size_policy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)


def _queue_row_overlay_path(rect: QRect) -> QPainterPath:
    """Return the rounded overlay path for generation queue rows."""

    path = QPainterPath()
    path.addRoundedRect(QRectF(rect.adjusted(1, 1, -1, -1)), 6, 6)
    return path


class GenerationQueueItemRow(QFrame):
    """Display one queued generation job and emit row-level user intents."""

    cancelRequested = Signal(str)
    removeRequested = Signal(str)
    openSnapshotRequested = Signal(str)
    bodyPressed = Signal(str, object)
    bodyMoved = Signal(str, object)
    bodyReleased = Signal(str, object)

    def __init__(
        self,
        row: QueueJobRowView,
        parent: QWidget | None = None,
        *,
        surface_mode: QueueSurfaceMode = "panel",
    ) -> None:
        """Create row labels and the optional cancel button."""

        super().__init__(parent)
        qt = cast(Any, Qt)
        self._row = row
        self._surface_mode = surface_mode
        self._is_dragging = False
        self._is_drag_source_hidden = False
        self._body_drag_targets: list[QWidget] = []
        self._tooltip_filter: object | None = None
        self._full_title = ""
        self._full_subtitle = ""
        self.setObjectName("GenerationQueueItemRow")
        self._interaction = RowInteractionFeedback(
            self,
            overlay_path=_queue_row_overlay_path,
            feedback_enabled=row.interaction_role == "draggable",
            manage_cursor=False,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 6, 8)
        layout.setSpacing(8)

        self._thumbnail_label = QLabel(self)
        self._thumbnail_label.setObjectName("GenerationQueueItemThumbnail")
        self._thumbnail_label.setFixedSize(
            _THUMBNAIL_SIZE.width(),
            _THUMBNAIL_SIZE.height(),
        )
        self._thumbnail_label.setAlignment(getattr(qt, "AlignCenter", qt.AlignVCenter))
        self._thumbnail_label.setStyleSheet(_queue_thumbnail_stylesheet())
        layout.addWidget(self._thumbnail_label, 0, qt.AlignVCenter)
        self._register_body_drag_target(self._thumbnail_label)

        self._text_column = QWidget(self)
        _allow_horizontal_shrink(self._text_column)
        text_layout = QVBoxLayout(self._text_column)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        self._title_label = StrongBodyLabel(self)
        _allow_horizontal_shrink(self._title_label)
        self._title_label.setObjectName("GenerationQueueItemTitle")
        self._title_label.setTextInteractionFlags(qt.NoTextInteraction)
        _set_label_point_size_delta(
            self._title_label,
            delta=_QUEUE_TITLE_FONT_DELTA,
            minimum=_QUEUE_MINIMUM_TITLE_POINT_SIZE,
        )
        self._title_label.setFixedHeight(_tight_label_height(self._title_label))

        self._subtitle_label = CaptionLabel(self)
        _allow_horizontal_shrink(self._subtitle_label)
        self._subtitle_label.setObjectName("GenerationQueueItemSubtitle")
        self._subtitle_label.setTextInteractionFlags(qt.NoTextInteraction)
        _set_label_point_size_delta(
            self._subtitle_label,
            delta=_QUEUE_SUBTITLE_FONT_DELTA,
            minimum=_QUEUE_MINIMUM_SUBTITLE_POINT_SIZE,
        )
        self._subtitle_label.setFixedHeight(_tight_label_height(self._subtitle_label))

        text_layout.addWidget(self._title_label)
        text_layout.addWidget(self._subtitle_label)
        layout.addWidget(self._text_column, 1)
        self._register_body_drag_target(self._text_column)
        self._register_body_drag_target(self._title_label)
        self._register_body_drag_target(self._subtitle_label)
        self._install_prompt_tooltip_filter(
            self,
            self._text_column,
            self._title_label,
            self._subtitle_label,
        )

        action_icon = FIF.DELETE if row.action == "remove" else FIF.CLOSE
        action_tooltip = "Remove job" if row.action == "remove" else "Cancel job"
        self._action_button = TransparentToolButton(action_icon, self)
        self._action_button.setToolTip(action_tooltip)
        self._action_button.setFixedSize(28, 28)
        self._action_button.setCursor(qt.PointingHandCursor)
        self._action_button.setVisible(row.action is not None)
        self._action_button.clicked.connect(
            lambda: self._emit_action_request(self._row.job_id, self._row.action)
        )
        layout.addWidget(self._action_button, 0, qt.AlignRight | qt.AlignVCenter)
        connect_theme_refresh(self, self._apply_role_style)
        self.set_row(row)

    def set_row(self, row: QueueJobRowView) -> None:
        """Update row content and interaction state without rebuilding layout."""

        self._row = row
        self._full_title = row.title
        self._full_subtitle = row.subtitle
        self._set_tooltip(self._row_body_tooltip(row))
        self._apply_text_elision()
        self._update_thumbnail(row)
        self._update_action_button(row)
        set_mouse_tracking = getattr(self, "setMouseTracking", None)
        if callable(set_mouse_tracking):
            set_mouse_tracking(row.interaction_role == "draggable")
        if row.interaction_role != "draggable":
            self._interaction.clear_transient_state()
            self._is_dragging = False
            self._is_drag_source_hidden = False
        self._interaction.set_feedback_enabled(row.interaction_role == "draggable")
        self._interaction.set_forced_hovered(row.visual_role == "active")
        self._apply_role_style()
        self._apply_body_cursor()
        self.update()

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        """Refresh elided label text after row geometry changes."""

        resize_event = getattr(super(), "resizeEvent", None)
        if callable(resize_event):
            resize_event(cast(Any, event))
        self._apply_text_elision()

    def showEvent(self, event: object) -> None:  # noqa: N802
        """Refresh elided label text once Qt has concrete row geometry."""

        show_event = getattr(super(), "showEvent", None)
        if callable(show_event):
            show_event(cast(Any, event))
        self._apply_text_elision()

    def _emit_action_request(self, job_id: str, action: object) -> None:
        """Emit the row intent matching the configured action."""

        if action == "remove":
            self.removeRequested.emit(job_id)
            return
        if action == "cancel":
            self.cancelRequested.emit(job_id)

    def set_dragging(self, dragging: bool) -> None:
        """Apply or clear active drag cursor and styling."""

        if self._is_dragging == dragging:
            return
        self._is_dragging = dragging
        self._interaction.set_pressed(dragging)
        self._apply_body_cursor()
        self.update()

    def set_drag_source_hidden(self, hidden: bool) -> None:
        """Hide the source row body while a floating reorder proxy represents it."""

        if self._is_drag_source_hidden == hidden:
            return
        self._is_drag_source_hidden = hidden
        self.setVisible(not hidden)
        self.update()

    def mousePressEvent(self, event: object) -> None:
        """Emit a row-body press for container-owned drag handling."""

        self._emit_body_pointer_event(event, self, self.bodyPressed, "press")
        super().mousePressEvent(cast(Any, event))

    def mouseMoveEvent(self, event: object) -> None:
        """Emit a row-body move for container-owned drag handling."""

        self._emit_body_pointer_event(event, self, self.bodyMoved, "move")
        super().mouseMoveEvent(cast(Any, event))

    def mouseReleaseEvent(self, event: object) -> None:
        """Emit a row-body release for container-owned drag handling."""

        self._emit_body_pointer_event(event, self, self.bodyReleased, "release")
        super().mouseReleaseEvent(cast(Any, event))

    def eventFilter(self, watched: object, event: object) -> bool:
        """Start pending-row drag gestures from row body child widgets."""

        if watched not in self._body_drag_targets:
            return bool(super().eventFilter(cast(Any, watched), cast(Any, event)))
        if _is_event_type(event, _qt_event_type("MouseButtonPress")):
            self._emit_body_pointer_event(event, watched, self.bodyPressed, "press")
            return False
        if _is_event_type(event, _qt_event_type("MouseMove")):
            return self._emit_body_pointer_event(event, watched, self.bodyMoved, "move")
        if _is_event_type(event, _qt_event_type("MouseButtonRelease")):
            return self._emit_body_pointer_event(
                event, watched, self.bodyReleased, "release"
            )
        return False

    def enterEvent(self, event: object) -> None:  # noqa: N802
        """Track row hover state for painted interaction overlays."""

        self._interaction.set_hovered(True)
        super().enterEvent(cast(Any, event))

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        """Clear hover and press state when the pointer leaves the row."""

        self._interaction.set_hovered(False)
        if not self._is_dragging:
            self._interaction.set_pressed(False)
        super().leaveEvent(cast(Any, event))

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint the row and then the Settings-style interaction overlay."""

        super().paintEvent(event)
        if QPainter is None:
            return
        painter = QPainter(self)
        self._interaction.paint_overlay(painter)

    def contextMenuEvent(self, event: object) -> None:
        """Show terminal-job context actions when available."""

        if not self._row.can_open_snapshot:
            return
        try:
            from qfluentwidgets import MenuAnimationType

            from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
            from substitute.presentation.widgets.qfluent_menu_renderer import (
                QFluentMenuRenderer,
            )
        except ImportError:
            return

        menu = QFluentMenuRenderer(parent=self).render(
            MenuModel(
                entries=(
                    MenuItem(
                        "generation_queue.open_snapshot",
                        "Open as Workflow Tab",
                        callback=self._emit_open_snapshot_request,
                        icon=FIF.ADD,
                    ),
                )
            )
        )
        global_pos = getattr(event, "globalPos", None)
        if callable(global_pos):
            menu.exec(global_pos(), aniType=MenuAnimationType.DROP_DOWN)

    def _emit_open_snapshot_request(self) -> None:
        """Emit the row snapshot-open intent."""

        self.openSnapshotRequested.emit(self._row.job_id)

    def _set_tooltip(self, tooltip: str | None) -> None:
        """Apply one tooltip to the row and text labels."""

        text = tooltip or ""
        self.setToolTip(text)
        self._title_label.setToolTip("")
        self._subtitle_label.setToolTip("")
        self._text_column.setToolTip("")

    @staticmethod
    def _row_body_tooltip(row: QueueJobRowView) -> str | None:
        """Return the tooltip content for the row body."""

        if row.status != "Failed" or row.tooltip is None:
            return row.prompt_tooltip or row.tooltip
        if row.prompt_tooltip is None:
            return row.tooltip
        return f"{row.tooltip}\n\nPrompt preview:\n{row.prompt_tooltip}"

    def _install_prompt_tooltip_filter(self, *widgets: QWidget) -> None:
        """Install one row-owned cursor tooltip filter on body tooltip targets."""

        self._tooltip_filter = install_cursor_tooltip_filter(
            self,
            *widgets,
            show_delay_ms=600,
        )

    @staticmethod
    def _set_label_text(label: QLabel, text: str) -> None:
        """Set label text across real Qt widgets and lightweight stubs."""

        set_text = getattr(label, "setText", None)
        if callable(set_text):
            set_text(text)
            return
        setattr(label, "text", text)

    def _apply_text_elision(self) -> None:
        """Elide title and subtitle labels to the available text-column width."""

        available_width = self._available_text_width()
        self._set_label_text(
            self._title_label,
            self._elided_label_text(
                self._title_label, self._full_title, available_width
            ),
        )
        self._set_label_text(
            self._subtitle_label,
            self._elided_label_text(
                self._subtitle_label,
                self._full_subtitle,
                available_width,
            ),
        )

    def _available_text_width(self) -> int | None:
        """Return the current width available for queue row text."""

        for widget in (self._text_column, self._title_label, self._subtitle_label):
            contents_rect = getattr(widget, "contentsRect", None)
            if callable(contents_rect):
                rect = contents_rect()
                width = getattr(rect, "width", None)
                if callable(width):
                    return max(0, int(width()))
            widget_width = getattr(widget, "width", None)
            if callable(widget_width):
                width_value = int(widget_width())
                if width_value >= 0:
                    return width_value
        return None

    @staticmethod
    def _elided_label_text(
        label: QLabel,
        text: str,
        available_width: int | None,
    ) -> str:
        """Return label text right-elided to one pixel width when possible."""

        if available_width is None:
            return text
        font_getter = getattr(label, "font", None)
        if not callable(font_getter):
            return text
        metrics = QFontMetrics(cast(Any, font_getter()))
        elided_text = getattr(metrics, "elidedText", None)
        if not callable(elided_text):
            return text
        return cast(
            str,
            elided_text(
                text,
                _qt_text_elide_mode("ElideRight"),
                max(0, available_width),
            ),
        )

    def _update_thumbnail(self, row: QueueJobRowView) -> None:
        """Refresh the lazy thumbnail for the current row."""

        clear = getattr(self._thumbnail_label, "clear", None)
        if callable(clear):
            clear()
        if row.thumbnail_path is None:
            return
        pixmap = _THUMBNAIL_CACHE.thumbnail(row.thumbnail_path, _THUMBNAIL_SIZE)
        if pixmap is not None:
            self._thumbnail_label.setPixmap(pixmap)

    def _update_action_button(self, row: QueueJobRowView) -> None:
        """Refresh the action button icon, tooltip, and visibility."""

        action_icon = FIF.DELETE if row.action == "remove" else FIF.CLOSE
        set_icon = getattr(self._action_button, "setIcon", None)
        if callable(set_icon):
            set_icon(action_icon)
        action_tooltip = "Remove job" if row.action == "remove" else "Cancel job"
        self._action_button.setToolTip(action_tooltip)
        self._action_button.setVisible(row.action is not None)

    def _apply_body_cursor(self) -> None:
        """Apply the cursor that matches the row interaction role."""

        cursor = self._current_body_cursor()
        self.setCursor(cast(Any, cursor))
        for target in self._body_drag_targets:
            target.setCursor(cast(Any, cursor))

    def _current_body_cursor(self) -> object:
        """Return the cursor matching the current row interaction state."""

        qt = cast(Any, Qt)
        cursor = _qt_cursor(qt, "ArrowCursor", "ArrowCursor")
        if self._row.interaction_role == "draggable":
            cursor = (
                _qt_cursor(qt, "ClosedHandCursor", "ClosedHandCursor")
                if self._is_dragging
                else _qt_cursor(qt, "OpenHandCursor", "OpenHandCursor")
            )
        return cursor

    def _apply_role_style(self) -> None:
        """Apply row styling for the current visual and surface roles."""

        base_background, border = _queue_row_surface_colors(self._row)
        self._thumbnail_label.setStyleSheet(_queue_thumbnail_stylesheet())
        self.setStyleSheet(
            f"""
            QFrame#GenerationQueueItemRow {{
                background: {base_background};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            """
        )

    def _register_body_drag_target(self, widget: QWidget) -> None:
        """Register one non-button child widget as a row body drag target."""

        self._body_drag_targets.append(widget)
        install_event_filter = getattr(widget, "installEventFilter", None)
        if callable(install_event_filter):
            install_event_filter(self)
        if self._row.interaction_role == "draggable":
            widget.setCursor(cast(Any, self._current_body_cursor()))

    def _emit_body_pointer_event(
        self,
        event: object,
        source: object,
        signal: object,
        event_kind: Literal["press", "move", "release"],
    ) -> bool:
        """Emit a low-level body pointer event for container-owned drag handling."""

        if self._row.interaction_role != "draggable":
            return False
        if event_kind == "press" and not is_left_mouse_press(event):
            return False
        if event_kind == "press":
            self._interaction.set_pressed(True)
        elif event_kind == "release":
            self._interaction.set_pressed(False)
        emit = getattr(signal, "emit", None)
        if not callable(emit):
            return False
        emit(self._row.job_id, self._event_parent_position(event, source))
        return event_kind == "move" and self._is_dragging

    def _event_row_position(self, event: object, source: object) -> QPoint:
        """Return an event position mapped into row coordinates."""

        position = getattr(event, "pos", None)
        if not callable(position):
            return QPoint()
        local_position = position()
        if source is self:
            return cast(QPoint, local_position)
        map_to_row = getattr(source, "mapTo", None)
        if callable(map_to_row):
            return cast(QPoint, map_to_row(self, local_position))
        return cast(QPoint, local_position)

    def _event_parent_position(self, event: object, source: object) -> object:
        """Return the event position mapped into the parent row container."""

        parent_getter = getattr(self, "parent", None)
        parent = parent_getter() if callable(parent_getter) else None
        map_from_global = getattr(parent, "mapFromGlobal", None)
        if callable(map_from_global):
            global_position = getattr(event, "globalPosition", None)
            if callable(global_position):
                return map_from_global(global_position().toPoint())
            global_pos = getattr(event, "globalPos", None)
            if callable(global_pos):
                return map_from_global(global_pos())
        row_position = self._event_row_position(event, source)
        map_to_parent = getattr(self, "mapToParent", None)
        if callable(map_to_parent):
            return map_to_parent(row_position)
        return row_position


def _is_event_type(event: object, expected_type: object) -> bool:
    """Return whether an event object reports the requested event type."""

    event_type = getattr(event, "type", None)
    return callable(event_type) and event_type() == expected_type


def _qt_event_type(name: str) -> object:
    """Return a QEvent type across Qt enum layouts and lightweight stubs."""

    type_namespace = getattr(QEvent, "Type", None)
    namespaced_value = getattr(type_namespace, name, None)
    if namespaced_value is not None:
        return namespaced_value
    return getattr(QEvent, name, name)


def _qt_cursor(qt: object, flat_name: str, cursor_shape_name: str) -> object:
    """Return a Qt cursor enum value across Qt versions and test stubs."""

    flat_value = getattr(qt, flat_name, None)
    if flat_value is not None:
        return flat_value
    cursor_shape = getattr(qt, "CursorShape", None)
    return getattr(cursor_shape, cursor_shape_name, flat_name)


def _qt_text_elide_mode(name: str) -> object:
    """Return a Qt text-elide enum value across Qt versions and test stubs."""

    text_elide_mode = getattr(Qt, "TextElideMode", None)
    namespaced_value = getattr(text_elide_mode, name, None)
    if namespaced_value is not None:
        return namespaced_value
    return getattr(Qt, name, name)


__all__ = ["GenerationQueueItemRow", "QueueSurfaceMode"]
