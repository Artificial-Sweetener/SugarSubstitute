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

"""Present one localized icon command inside a Contextual Toolbar row."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIconBase, TransparentToolButton  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import ApplicationMessage
from sugarsubstitute_shared.presentation.localization import (
    set_localized_accessible_name,
    set_localized_tooltip,
)

from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
)


class ContextualToolbarCommandButton(TransparentToolButton):  # type: ignore[misc]
    """Render one canonical icon-only command with localized semantics."""

    def __init__(
        self,
        icon: FluentIconBase,
        label: ApplicationMessage,
        parent: QWidget,
    ) -> None:
        """Bind icon, canonical row geometry, and accessible copy."""
        super().__init__(parent)
        self.setIcon(cast(Any, icon))
        self.setFixedSize(CANVAS_CHROME_CONTROL_HEIGHT, CANVAS_CHROME_CONTROL_HEIGHT)
        self.setIconSize(QSize(20, 20))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        set_localized_tooltip(self, label.source_text, *label.arguments)
        set_localized_accessible_name(self, label.source_text, *label.arguments)


__all__ = ["ContextualToolbarCommandButton"]
