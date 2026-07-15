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

"""Build editor node-card widgets from resolved node behavior and live node state."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Mapping

from PySide6.QtCore import (
    QEvent,
    QTimer,
    QRect,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QResizeEvent,
    QShowEvent,
    QTransform,
)
from PySide6.QtWidgets import QLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF
from shiboken6 import isValid

try:
    from qfluentwidgets.common.font import setFont  # type: ignore[import-untyped]
    from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
        isDarkTheme,
    )
except ImportError:  # pragma: no cover - test-stub fallback only

    def setFont(_widget: object, _font_size: int = 14, _weight: int = 50) -> None:
        """Provide a no-op font helper when qfluentwidgets font utilities are unavailable."""

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True


from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
    resolved_backdrop_mode,
    winui_card_border_color,
    winui_card_fill_color,
)
from substitute.presentation.widgets.row_interaction_feedback import (
    RowInteractionFeedback,
)
from substitute.presentation.widgets.model_picker import ModelPickerField
from substitute.shared.logging.logger import (
    get_logger,
)

from substitute.presentation.editor.panel.widgets.field_row import (
    EDITOR_ROW_BODY_SPACING,
    EDITOR_ROW_HEIGHT,
)

_LOGGER = get_logger("presentation.editor.panel.widgets.node_card")
NODE_CARD_TITLE_ICON_SLOT_SIZE = 24
NODE_CARD_TITLE_ICON_SIZE = 20
_NODE_CARD_CORNER_RADIUS = 4.0
_NODE_CARD_SURFACE_VERTICAL_PADDING = EDITOR_ROW_BODY_SPACING
NODE_CARD_TITLE_HEIGHT = EDITOR_ROW_HEIGHT + (_NODE_CARD_SURFACE_VERTICAL_PADDING * 2)
NODE_CARD_BODY_TOP_PADDING = 0
NODE_CARD_BODY_BOTTOM_PADDING = 0
NODE_CARD_BODY_ROW_SPACING = 0
_QT_WIDGET_MAXIMUM_SIZE = 16_777_215


def _node_card_background_color(widget: QWidget | None = None) -> QColor:
    """Return the node-card background color for the active theme."""

    _ = isDarkTheme()
    return QColor(*winui_card_fill_color(resolved_backdrop_mode(widget)))


def _node_card_border_color() -> QColor:
    """Return the node-card border color for the active theme."""

    _ = isDarkTheme()
    return QColor(*winui_card_border_color())


def _is_live_widget(widget: object) -> bool:
    """Return whether one Qt widget can still be safely inspected."""

    try:
        return bool(isValid(widget))
    except TypeError:
        return True


class NodeCardWidget(QWidget):
    """Provide the root widget for one node card built under an editor parent."""

    def __init__(self, parent: QWidget) -> None:
        """Create a transparent node-card root that cannot become top-level."""

        super().__init__(parent)
        self.setObjectName("NodeCardWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


class _NodeCardSurface(QWidget):
    """Compose node-card header and content surfaces without monolithic painting."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create one transparent node-card composition root."""

        super().__init__(parent)
        self.setObjectName("NodeCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._model_picker_width_sync_pending = False

    def defer_model_picker_width_group_sync(self) -> None:
        """Defer shared model-picker width sync until card layout has settled."""

        if self._model_picker_width_sync_pending:
            return
        if not self._model_picker_width_group_fields():
            return
        self._model_picker_width_sync_pending = True
        QTimer.singleShot(0, self.sync_model_picker_width_group)

    def sync_model_picker_width_group(self) -> None:
        """Apply one shared width cap to visible model pickers in this node card."""

        self._model_picker_width_sync_pending = False
        fields = self._model_picker_width_group_fields()
        if len(fields) < 2:
            self._release_model_picker_width_caps(fields)
            return
        self._release_model_picker_width_caps(fields)
        self._activate_model_picker_width_layouts(fields)
        visible_fields = [
            field
            for field in fields
            if _is_live_widget(field) and field.isVisibleTo(self) and field.width() > 0
        ]
        if len(visible_fields) < 2:
            return
        shared_width = min(field.width() for field in visible_fields)
        for field in visible_fields:
            field.setMinimumWidth(shared_width)
            field.setMaximumWidth(shared_width)
            self._set_model_picker_layout_alignment(
                field,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            field.updateGeometry()
        self._activate_model_picker_width_layouts(visible_fields)

    def _model_picker_width_group_fields(self) -> list[ModelPickerField]:
        """Return live model picker fields under this node card."""

        return [
            widget
            for widget in self.findChildren(ModelPickerField)
            if _is_live_widget(widget)
        ]

    def _release_model_picker_width_caps(
        self,
        fields: list[ModelPickerField],
    ) -> None:
        """Remove prior shared caps so wider card layouts can be measured."""

        for field in fields:
            if not _is_live_widget(field):
                continue
            if field.minimumWidth() != 0:
                field.setMinimumWidth(0)
            if field.maximumWidth() != _QT_WIDGET_MAXIMUM_SIZE:
                field.setMaximumWidth(_QT_WIDGET_MAXIMUM_SIZE)
            self._set_model_picker_layout_alignment(
                field,
                Qt.AlignmentFlag.AlignVCenter,
            )
            field.updateGeometry()

    def _set_model_picker_layout_alignment(
        self,
        field: ModelPickerField,
        alignment: Qt.AlignmentFlag,
    ) -> None:
        """Set parent-layout alignment for a picker without changing row ownership."""

        parent = field.parentWidget()
        if parent is None or not _is_live_widget(parent):
            return
        layout = parent.layout()
        if layout is None:
            return
        layout.setAlignment(field, alignment)

    def _activate_model_picker_width_layouts(
        self,
        fields: list[ModelPickerField],
    ) -> None:
        """Ask affected layouts to recompute before measuring model picker widths."""

        layouts: list[QLayout] = []
        seen_layout_ids: set[int] = set()
        for widget in (self, *fields):
            if not _is_live_widget(widget):
                continue
            current: QWidget | None = widget
            while current is not None and _is_live_widget(current):
                layout = current.layout()
                if layout is not None and id(layout) not in seen_layout_ids:
                    seen_layout_ids.add(id(layout))
                    layouts.append(layout)
                if current is self:
                    break
                current = current.parentWidget()
        for layout in layouts:
            layout.invalidate()
        for layout in reversed(layouts):
            layout.activate()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Refresh model picker widths after the card resizes."""

        super().resizeEvent(event)
        self.defer_model_picker_width_group_sync()

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh model picker widths after the card becomes visible."""

        super().showEvent(event)
        self.defer_model_picker_width_group_sync()


class _NodeCardPaintSurface(QWidget):
    """Paint one rounded node-card segment with configurable attached corners."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create one themed paint surface."""

        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._content_attached = False
        connect_theme_refresh(self, self.update)

    def set_accordion_content_attached(self, attached: bool) -> None:
        """Set whether this surface is visually attached to another card segment."""

        self._content_attached = attached
        self.update()

    def accordion_content_attached(self) -> bool:
        """Return whether this segment is currently attached to another segment."""

        return self._content_attached

    def paintEvent(self, event: object) -> None:
        """Paint the themed card segment without styling descendants."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Keep fill and stroke geometry separate. The fill must cover the full widget
        # rect so attached header/body seams do not reveal the darker transparent
        # parent background. The stroke stays inset to avoid clipping the outer border.
        fill_rect = self.rect()
        stroke_rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_node_card_background_color(self))
        painter.drawPath(self._paint_path(fill_rect))
        painter.setPen(QPen(_node_card_border_color(), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._stroke_path(stroke_rect))

    def _paint_path(self, rect: QRect) -> QPainterPath:
        """Return the rounded segment path for the current attachment state."""

        path = QPainterPath()
        x = float(rect.x())
        y = float(rect.y())
        width = float(rect.width())
        height = float(rect.height())
        radius = min(_NODE_CARD_CORNER_RADIUS, width / 2.0, height / 2.0)
        top_left = self._top_left_radius(radius)
        top_right = self._top_right_radius(radius)
        bottom_right = self._bottom_right_radius(radius)
        bottom_left = self._bottom_left_radius(radius)

        path.moveTo(x + top_left, y)
        path.lineTo(x + width - top_right, y)
        if top_right:
            path.quadTo(x + width, y, x + width, y + top_right)
        path.lineTo(x + width, y + height - bottom_right)
        if bottom_right:
            path.quadTo(x + width, y + height, x + width - bottom_right, y + height)
        path.lineTo(x + bottom_left, y + height)
        if bottom_left:
            path.quadTo(x, y + height, x, y + height - bottom_left)
        path.lineTo(x, y + top_left)
        if top_left:
            path.quadTo(x, y, x + top_left, y)
        path.closeSubpath()
        return path

    def _stroke_path(self, rect: QRect) -> QPainterPath:
        """Return the border path for this surface."""

        return self._paint_path(rect)

    def _top_left_radius(self, radius: float) -> float:
        """Return the top-left corner radius for this surface."""

        return radius

    def _top_right_radius(self, radius: float) -> float:
        """Return the top-right corner radius for this surface."""

        return radius

    def _bottom_right_radius(self, radius: float) -> float:
        """Return the bottom-right corner radius for this surface."""

        return radius

    def _bottom_left_radius(self, radius: float) -> float:
        """Return the bottom-left corner radius for this surface."""

        return radius


class _NodeCardHeaderSurface(_NodeCardPaintSurface):
    """Paint and host the stable accordion header segment."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the stable header paint surface."""

        super().__init__(parent)
        self.setObjectName("NodeCardHeaderSurface")
        self._interaction = RowInteractionFeedback(
            self,
            overlay_path=lambda rect: self._paint_path(rect.adjusted(0, 0, -1, -1)),
        )

    def set_interactive_targets(self, targets: Iterable[QWidget]) -> None:
        """Track child widgets that should delegate body clicks to the title row."""

        self._interaction.set_interactive_targets(targets)

    def set_row_activation(self, callback: Callable[[], None] | None) -> None:
        """Set the row-level title action and synchronize pointer feedback."""

        self._interaction.set_activation(callback)

    def clear_row_activation(self) -> None:
        """Disable row-level title action and clear transient pointer state."""

        self._interaction.set_activation(None)

    def row_activation_enabled(self) -> bool:
        """Return whether the title row currently has row-level behavior."""

        return self._interaction.has_activation()

    def eventFilter(self, watched: object, event: object) -> bool:
        """Route non-control child clicks through the title-row activation policy."""

        if self._interaction.eventFilter(watched, event):
            return True
        return bool(super().eventFilter(watched, event))

    def enterEvent(self, event: QEvent) -> None:
        """Apply pointer-over feedback when the title row has row behavior."""

        self._interaction.set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear transient title-row pointer feedback when leaving the row."""

        self._interaction.clear_transient_state()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Track row-body presses for activation feedback."""

        if event is None:
            self._interaction.activate()
            return
        if self._interaction.handle_mouse_press(event):
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Activate the title row from a released row-body click."""

        if self._interaction.handle_mouse_release(event):
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: object) -> None:
        """Paint the header surface plus any row interaction overlay."""

        super().paintEvent(event)
        painter = QPainter(self)
        self._interaction.paint_overlay(painter)

    def _stroke_path(self, rect: QRect) -> QPainterPath:
        """Return the header border path without the attached body seam."""

        if not self._content_attached:
            return super()._stroke_path(rect)

        # Do not draw the bottom header stroke while body content is attached. The
        # title/body boundary is a divider inside the content surface, matching the
        # field-row divider compositing path. Reintroducing this stroke makes the first
        # field row appear shorter and the seam darker than the field-to-field lines.
        path = QPainterPath()
        x = float(rect.x())
        y = float(rect.y())
        width = float(rect.width())
        height = float(rect.height())
        radius = min(_NODE_CARD_CORNER_RADIUS, width / 2.0, height / 2.0)
        top_left = self._top_left_radius(radius)
        top_right = self._top_right_radius(radius)

        path.moveTo(x, y + height)
        path.lineTo(x, y + top_left)
        if top_left:
            path.quadTo(x, y, x + top_left, y)
        path.lineTo(x + width - top_right, y)
        if top_right:
            path.quadTo(x + width, y, x + width, y + top_right)
        path.lineTo(x + width, y + height)
        return path

    def _bottom_right_radius(self, radius: float) -> float:
        """Square the bottom-right corner while body content is attached."""

        return 0.0 if self._content_attached else radius

    def _bottom_left_radius(self, radius: float) -> float:
        """Square the bottom-left corner while body content is attached."""

        return 0.0 if self._content_attached else radius


class _NodeCardContentSurface(_NodeCardPaintSurface):
    """Paint and host the moving accordion content segment."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the moving content paint surface."""

        super().__init__(parent)
        self.setObjectName("NodeCardContentSurface")

    def _top_left_radius(self, radius: float) -> float:
        """Square the top-left corner while attached to the header."""

        return 0.0 if self._content_attached else radius

    def _top_right_radius(self, radius: float) -> float:
        """Square the top-right corner while attached to the header."""

        return 0.0 if self._content_attached else radius

    def _stroke_path(self, rect: QRect) -> QPainterPath:
        """Return the content border path without repainting the attached top edge."""

        if not self._content_attached:
            return super()._stroke_path(rect)

        path = QPainterPath()
        x = float(rect.x())
        y = float(rect.y())
        width = float(rect.width())
        height = float(rect.height())
        radius = min(_NODE_CARD_CORNER_RADIUS, width / 2.0, height / 2.0)
        bottom_right = self._bottom_right_radius(radius)
        bottom_left = self._bottom_left_radius(radius)

        path.moveTo(x + width, y)
        path.lineTo(x + width, y + height - bottom_right)
        if bottom_right:
            path.quadTo(x + width, y + height, x + width - bottom_right, y + height)
        path.lineTo(x + bottom_left, y + height)
        if bottom_left:
            path.quadTo(x, y + height, x, y + height - bottom_left)
        path.lineTo(x, y)
        return path


def reconcile_node_card_body_separators(
    row_widgets: Mapping[object, tuple[object | None, object | None]],
) -> None:
    """Show body separators only between adjacent visible node-card rows."""

    for layout in _body_layouts_from_row_widgets(row_widgets):
        _reconcile_layout_separators(layout)


def _body_layouts_from_row_widgets(
    row_widgets: Mapping[object, tuple[object | None, object | None]],
) -> list[QVBoxLayout]:
    """Return unique node-card body layouts discovered from tracked rows."""

    layouts: list[QVBoxLayout] = []
    seen_layout_ids: set[int] = set()
    for _separator, row in row_widgets.values():
        if not isinstance(row, QWidget) or not _is_live_widget(row):
            continue
        parent = row.parentWidget()
        if parent is None:
            continue
        layout = parent.layout()
        if not isinstance(layout, QVBoxLayout) or id(layout) in seen_layout_ids:
            continue
        seen_layout_ids.add(id(layout))
        layouts.append(layout)
    return layouts


def _reconcile_layout_separators(content_layout: QVBoxLayout) -> None:
    """Apply visible-row adjacency to one node-card body layout."""

    previous_visible_row = False
    pending_separator: QWidget | None = None
    for index in range(content_layout.count()):
        item = content_layout.itemAt(index)
        widget = item.widget() if item is not None else None
        if widget is None or not _is_live_widget(widget):
            continue
        if _is_title_body_divider(widget):
            # The title/body divider is the authoritative seam above the first visible
            # row. Treating it like a body separator makes hidden leading rows expose
            # the next field divider at the title seam and darkens the boundary.
            continue
        if _is_body_separator(widget):
            if pending_separator is not None:
                pending_separator.setVisible(False)
            pending_separator = widget
            continue

        row_visible = not widget.isHidden()
        if pending_separator is not None:
            pending_separator.setVisible(row_visible and previous_visible_row)
            pending_separator = None
        if row_visible:
            previous_visible_row = True

    if pending_separator is not None:
        pending_separator.setVisible(False)


def _is_body_separator(widget: QWidget) -> bool:
    """Return whether one content-layout widget is a body row separator."""

    return widget.property("divider_for_field") is not None


def _is_title_body_divider(widget: QWidget) -> bool:
    """Return whether one divider belongs to the title/body boundary."""

    return widget.property("title_body_divider") is True


def rotate_icon(icon_enum: FIF, angle: int) -> QPixmap:
    """Return a rotated pixmap for one Fluent icon."""

    pixmap = icon_enum.icon().pixmap(20, 20)
    transform = QTransform().rotate(angle)
    return pixmap.transformed(transform, Qt.SmoothTransformation)


__all__ = [
    "NodeCardWidget",
    "reconcile_node_card_body_separators",
    "rotate_icon",
]
