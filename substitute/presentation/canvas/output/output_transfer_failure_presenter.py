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

"""Present localized non-blocking feedback for Output transfer failures."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from qfluentwidgets import InfoBar  # type: ignore[import-untyped]
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)


class OutputTransferFailurePresenter:
    """Own user-facing drag and clipboard transfer failure feedback."""

    def __init__(self, parent: QWidget) -> None:
        """Bind non-blocking failure feedback to the Output surface."""

        self._parent = parent

    def report_copy_failure(self, _reason: str) -> None:
        """Present one localized failure without exposing technical detail."""

        InfoBar.error(
            title=render_application_text(app_text("Copy")),
            content=render_application_text(app_text("Unable to copy output image.")),
            duration=5000,
            parent=self._parent.window(),
        )

    def report_drag_failure(self, _reason: str) -> None:
        """Present one localized drag failure without exposing technical detail."""

        InfoBar.error(
            title=render_application_text(app_text("Drag")),
            content=render_application_text(
                app_text("Unable to transfer output image.")
            ),
            duration=5000,
            parent=self._parent.window(),
        )


__all__ = ["OutputTransferFailurePresenter"]
