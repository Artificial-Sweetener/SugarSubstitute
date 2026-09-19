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

"""Own shared installer page geometry and heading composition."""

from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF, IconWidget  # type: ignore[import-untyped]
from sugarsubstitute_shared.presentation.installer_surface import (
    INSTALLER_CONTENT_MAX_WIDTH,
)


def configure_installer_page(page: QFrame, object_name: str) -> QVBoxLayout:
    """Apply the shared readable page width and content spacing."""
    page.setObjectName(object_name)
    page.setMinimumWidth(760)
    page.setMaximumWidth(INSTALLER_CONTENT_MAX_WIDTH)
    page.setProperty("installerContentWidth", INSTALLER_CONTENT_MAX_WIDTH)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(12)
    return layout


def create_installer_page(
    parent: QWidget, object_name: str
) -> tuple[QFrame, QVBoxLayout]:
    """Create a page using the same geometry as dedicated installer surfaces."""
    page = QFrame(parent)
    return page, configure_installer_page(page, object_name)


def build_installer_hero(
    page: QWidget,
    icon: FIF,
    *,
    centered: bool = False,
) -> tuple[QHBoxLayout, QVBoxLayout]:
    """Create a compact icon-and-heading row for one launcher page."""

    row = QHBoxLayout()
    row.setSpacing(16)
    if centered:
        row.addStretch(1)
    badge = QFrame(page)
    badge.setObjectName("OnboardingHeroBadge")
    badge_layout = QVBoxLayout(badge)
    badge_layout.setContentsMargins(11, 11, 11, 11)
    icon_widget = IconWidget(icon, badge)
    icon_widget.setFixedSize(24, 24)
    badge_layout.addWidget(icon_widget)
    row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
    text_layout = QVBoxLayout()
    text_layout.setSpacing(6)
    row.addLayout(text_layout, 0 if centered else 1)
    if centered:
        row.addStretch(1)
    return row, text_layout
