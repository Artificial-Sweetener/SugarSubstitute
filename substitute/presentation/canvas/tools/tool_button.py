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

"""Render one qfluent icon button for a contextual canvas tool."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QPaintEvent, QPainter, QPolygon
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    TransparentToolButton,
    themeColor,
)

from sugarsubstitute_shared.localization import ApplicationMessage
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    ToolTipPosition,
    ensure_fluent_tooltip_filter,
    set_fluent_tooltip_text,
)
from sugarsubstitute_shared.presentation.localization import (
    render_application_text,
    set_localized_accessible_name,
    set_localized_tooltip,
)

from .layout_projection import CanvasToolSlotPresentation

CANVAS_TOOL_BUTTON_SIZE = 34
CANVAS_TOOL_ICON_SIZE = 20


class CanvasToolButton(TransparentToolButton):  # type: ignore[misc]
    """Present one icon-only tool through qfluent's native hover interaction."""

    groupMenuRequested = Signal(str, QPoint)

    def __init__(
        self,
        presentation: CanvasToolSlotPresentation,
        parent: QWidget,
    ) -> None:
        """Initialize stable identity, geometry, semantics, and qfluent styling."""

        super().__init__(parent)
        self.slot_id = presentation.slot_id
        self.tool_id = presentation.tool_id
        self.kind = presentation.current.kind
        self._grouped = presentation.grouped
        self.setIcon(cast(Any, presentation.current.icon))
        self.setFixedSize(CANVAS_TOOL_BUTTON_SIZE, CANVAS_TOOL_BUTTON_SIZE)
        self.setIconSize(QSize(CANVAS_TOOL_ICON_SIZE, CANVAS_TOOL_ICON_SIZE))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setText("")
        self.setCheckable(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._bind_label(presentation)
        self.apply_presentation(presentation)

    def apply_presentation(self, presentation: CanvasToolSlotPresentation) -> None:
        """Apply authoritative availability without duplicating selection state."""

        self.tool_id = presentation.tool_id
        self.kind = presentation.current.kind
        self._grouped = presentation.grouped
        self.setIcon(cast(Any, presentation.current.icon))
        self._bind_label(presentation)
        self.setEnabled(presentation.current.enabled)
        self.update()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Request the member picker only when this slot contains a group."""

        if not self._grouped:
            event.ignore()
            return
        self.groupMenuRequested.emit(self.slot_id, event.globalPos())
        event.accept()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Render the qfluent button and a compact grouped-slot marker."""

        super().paintEvent(event)
        if not self._grouped:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(themeColor())
        right = self.width() - 5
        bottom = self.height() - 5
        painter.drawPolygon(
            QPolygon(
                (
                    QPoint(right - 4, bottom),
                    QPoint(right, bottom),
                    QPoint(right, bottom - 4),
                )
            )
        )

    def _bind_label(self, presentation: CanvasToolSlotPresentation) -> None:
        """Bind translated tooltips and accessible names to the icon button."""

        label = (
            presentation.current.unavailable_reason
            if not presentation.current.enabled
            and presentation.current.unavailable_reason is not None
            else presentation.current.label
        )
        if isinstance(label, ApplicationMessage):
            set_localized_tooltip(self, label.source_text, *label.arguments)
            set_localized_accessible_name(
                self,
                label.source_text,
                *label.arguments,
            )
        else:
            rendered = render_application_text(label)
            set_fluent_tooltip_text(self, rendered)
            self.setAccessibleName(rendered)
        ensure_fluent_tooltip_filter(
            self,
            position=ToolTipPosition.RIGHT,
            show_when_disabled=True,
        )


__all__ = [
    "CANVAS_TOOL_BUTTON_SIZE",
    "CANVAS_TOOL_ICON_SIZE",
    "CanvasToolButton",
]
