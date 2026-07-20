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

"""Localize the QFluent dialog surfaces invoked by SugarSubstitute."""

from __future__ import annotations

from functools import partial

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    ColorDialog,
    ColorPickerButton,
    MessageBoxBase,
)

from sugarsubstitute_shared.localization import ApplicationMessage, app_text
from sugarsubstitute_shared.presentation.localization import (
    render_application_text,
    set_localized_accessible_name,
    set_localized_text,
    set_localized_tooltip,
)


class LocalizedMessageBoxBase(MessageBoxBase):  # type: ignore[misc]
    """Own SugarSubstitute translations for QFluent message-box chrome."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Bind standard actions without replacing QFluent's dialog structure."""

        super().__init__(parent)
        set_localized_text(self.yesButton, "OK")
        set_localized_text(self.cancelButton, "Cancel")


class LocalizedColorDialog(ColorDialog):  # type: ignore[misc]
    """Own translations for the QFluent color dialog SugarSubstitute opens."""

    def __init__(
        self,
        color: QColor,
        title: ApplicationMessage,
        parent: QWidget | None = None,
        *,
        enable_alpha: bool = False,
    ) -> None:
        """Bind app catalog messages to QFluent's existing color controls."""

        super().__init__(
            color,
            render_application_text(title),
            parent,
            enableAlpha=enable_alpha,
        )
        self._bind_adjusted_label(self.titleLabel, title)
        self._bind_adjusted_label(self.editLabel, app_text("Edit Color"))
        self._bind_adjusted_label(self.redLabel, app_text("Red"))
        self._bind_adjusted_label(self.greenLabel, app_text("Green"))
        self._bind_adjusted_label(self.blueLabel, app_text("Blue"))
        self._bind_adjusted_label(self.opacityLabel, app_text("Opacity"))
        set_localized_text(self.yesButton, "OK")
        set_localized_text(self.cancelButton, "Cancel")

    @staticmethod
    def _bind_adjusted_label(target: QLabel, message: ApplicationMessage) -> None:
        """Bind one label and keep QFluent's absolute layout geometry current."""

        set_localized_text(
            target,
            message.source_text,
            *message.arguments,
            property_setter=partial(_set_adjusted_label_text, target),
        )


class LocalizedColorPickerButton(ColorPickerButton):  # type: ignore[misc]
    """Open SugarSubstitute's localized adapter around QFluent's color dialog."""

    def __init__(
        self,
        color: QColor,
        dialog_title: ApplicationMessage,
        parent: QWidget | None = None,
        *,
        enable_alpha: bool = False,
    ) -> None:
        """Replace only QFluent's construction-time dialog translation hook."""

        super().__init__(
            color,
            render_application_text(dialog_title),
            parent,
            enableAlpha=enable_alpha,
        )
        self._dialog_title = dialog_title
        self.clicked.disconnect()
        self.clicked.connect(self._show_localized_color_dialog)
        set_localized_accessible_name(
            self,
            dialog_title.source_text,
            *dialog_title.arguments,
        )
        set_localized_tooltip(
            self,
            dialog_title.source_text,
            *dialog_title.arguments,
        )

    def _create_color_dialog(self) -> LocalizedColorDialog:
        """Create the adapter while retaining QFluent's visual implementation."""

        return LocalizedColorDialog(
            self.color,
            self._dialog_title,
            self.window(),
            enable_alpha=self.enableAlpha,
        )

    def _show_localized_color_dialog(self) -> None:
        """Commit a selected color through QFluent's established public signal."""

        dialog = self._create_color_dialog()
        dialog.colorChanged.connect(self._commit_color)
        dialog.exec()

    def _commit_color(self, color: QColor) -> None:
        """Apply and publish one accepted dialog color."""

        self.setColor(color)
        self.colorChanged.emit(color)


def _set_adjusted_label_text(target: QLabel, text: str) -> None:
    """Update an absolute-layout QFluent label and its translated width."""

    target.setText(text)
    target.adjustSize()


__all__ = [
    "LocalizedColorDialog",
    "LocalizedColorPickerButton",
    "LocalizedMessageBoxBase",
]
