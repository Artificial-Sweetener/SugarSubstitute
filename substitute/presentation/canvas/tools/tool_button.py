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

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import TransparentToolButton  # type: ignore[import-untyped]

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

from .model import CanvasToolPresentation

CANVAS_TOOL_BUTTON_SIZE = 34
CANVAS_TOOL_ICON_SIZE = 20


class CanvasToolButton(TransparentToolButton):  # type: ignore[misc]
    """Present one icon-only tool through qfluent's native hover interaction."""

    def __init__(
        self,
        presentation: CanvasToolPresentation,
        parent: QWidget,
    ) -> None:
        """Initialize stable identity, geometry, semantics, and qfluent styling."""

        super().__init__(parent)
        self.tool_id = presentation.tool_id
        self.kind = presentation.kind
        self.setIcon(cast(Any, presentation.icon))
        self.setFixedSize(CANVAS_TOOL_BUTTON_SIZE, CANVAS_TOOL_BUTTON_SIZE)
        self.setIconSize(QSize(CANVAS_TOOL_ICON_SIZE, CANVAS_TOOL_ICON_SIZE))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setText("")
        self.setCheckable(False)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._bind_label(presentation)
        self.apply_presentation(presentation)

    def apply_presentation(self, presentation: CanvasToolPresentation) -> None:
        """Apply authoritative availability without duplicating selection state."""

        self.setEnabled(presentation.enabled)

    def _bind_label(self, presentation: CanvasToolPresentation) -> None:
        """Bind translated tooltips and accessible names to the icon button."""

        label = presentation.label
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
        ensure_fluent_tooltip_filter(self, position=ToolTipPosition.RIGHT)


__all__ = [
    "CANVAS_TOOL_BUTTON_SIZE",
    "CANVAS_TOOL_ICON_SIZE",
    "CanvasToolButton",
]
