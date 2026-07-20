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

"""Provide an inline InfoBar-style notification for Settings pages."""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    TransparentToolButton,
)
from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import apply_application_text

SettingsInfoBarSeverity = Literal["info", "success", "warning", "error"]

_SEVERITY_COLORS: dict[SettingsInfoBarSeverity, tuple[str, str]] = {
    "info": ("rgba(0, 120, 212, 34)", "rgba(0, 120, 212, 150)"),
    "success": ("rgba(16, 124, 16, 34)", "rgba(16, 124, 16, 150)"),
    "warning": ("rgba(255, 185, 0, 44)", "rgba(255, 185, 0, 170)"),
    "error": ("rgba(196, 43, 28, 38)", "rgba(196, 43, 28, 170)"),
}


class SettingsInfoBar(QFrame):
    """Show dismissible inline operation feedback inside a Settings page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a hidden Settings notification bar."""

        super().__init__(parent)
        self.setObjectName("SubstituteSettingsInfoBar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._severity: SettingsInfoBarSeverity = "info"
        self.title_label = BodyLabel("", self)
        self.title_label.setWordWrap(True)
        self.message_label = CaptionLabel("", self)
        self.message_label.setWordWrap(True)
        self.dismiss_button = TransparentToolButton(FluentIcon.CLOSE, self)
        self.dismiss_button.setFixedSize(28, 28)
        self.dismiss_button.clicked.connect(self.clear)
        self._build_layout()
        self.clear()

    def show_message(
        self,
        *,
        severity: SettingsInfoBarSeverity,
        title: ApplicationText,
        message: ApplicationText,
    ) -> None:
        """Render one notification and show the bar."""

        self._severity = severity
        apply_application_text(self.title_label, title)
        self.title_label.setVisible(bool(title.strip()))
        apply_application_text(self.message_label, message)
        self.message_label.setVisible(bool(message.strip()))
        self._apply_style()
        self.show()

    def clear(self) -> None:
        """Hide the current notification."""

        apply_application_text(self.title_label, "")
        apply_application_text(self.message_label, "")
        self.hide()

    def severity(self) -> SettingsInfoBarSeverity:
        """Return the severity currently assigned to the bar."""

        return self._severity

    def _build_layout(self) -> None:
        """Compose the notification layout."""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(12)
        text_column = QWidget(self)
        text_column.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        text_column.setStyleSheet("background-color: transparent; border: none;")
        text_layout = QVBoxLayout(text_column)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.message_label)
        layout.addWidget(text_column, 1)
        layout.addWidget(self.dismiss_button, 0, Qt.AlignmentFlag.AlignTop)

    def _apply_style(self) -> None:
        """Apply severity colors to the inline notification."""

        background, border = _SEVERITY_COLORS[self._severity]
        self.setStyleSheet(
            "QFrame#SubstituteSettingsInfoBar {"
            f"background-color: {background};"
            f"border: 1px solid {border};"
            "border-radius: 6px;"
            "}"
        )


__all__ = ["SettingsInfoBar", "SettingsInfoBarSeverity"]
