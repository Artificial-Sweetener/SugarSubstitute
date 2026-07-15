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

"""Compose dynamic Settings pages that are not fully catalog-rendered."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.presentation.settings.comfy_connection_page import (
    ComfyConnectionSettingsPage,
)
from substitute.presentation.settings.comfy_environment_page import ComfyEnvironmentPage
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_GROUP_TOP_MARGIN,
)


class ComfyUiSettingsPage(QWidget):
    """Compose ComfyUI connection and environment settings under one page."""

    def __init__(
        self,
        *,
        connection_page: ComfyConnectionSettingsPage,
        environment_page: ComfyEnvironmentPage,
        parent: QWidget | None = None,
    ) -> None:
        """Create the composite ComfyUI Settings page."""

        super().__init__(parent)
        self._connection_page = connection_page
        self._environment_page = environment_page
        self._build_layout()

    def refresh(self) -> None:
        """Refresh both ComfyUI child settings areas."""

        self._connection_page.reload()
        self._environment_page.refresh()

    def set_settings_page_active(self, active: bool) -> None:
        """Forward route/page activity to the embedded environment page."""

        self._environment_page.set_settings_page_active(active)

    def _build_layout(self) -> None:
        """Create the composite page layout."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_CARD_GROUP_TOP_MARGIN)
        layout.addWidget(self._connection_page)
        layout.addWidget(self._environment_page)
        layout.addStretch(1)


__all__ = ["ComfyUiSettingsPage"]
