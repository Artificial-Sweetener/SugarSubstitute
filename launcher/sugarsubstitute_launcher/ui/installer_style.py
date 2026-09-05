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

"""Apply theme-derived styling to the installer view and title bar."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QColor
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
    themeColor,
)
from sugarsubstitute_shared.presentation.installer_surface import (
    build_installer_surface_style_sheet,
)


def apply_installer_style(window: Any) -> None:
    """Style launcher surfaces while leaving Fluent controls authoritative."""

    accent = themeColor()
    accent_rgb = f"{accent.red()}, {accent.green()}, {accent.blue()}"
    text_rgb = "255, 255, 255" if isDarkTheme() else "0, 0, 0"
    wash_rgb = "255, 255, 255" if isDarkTheme() else "0, 0, 0"
    icon_color = QColor("#ffffff") if isDarkTheme() else QColor("#000000")
    hover_bg = QColor(45, 45, 45) if isDarkTheme() else QColor(0, 0, 0, 24)
    pressed_bg = QColor(30, 30, 30) if isDarkTheme() else QColor(0, 0, 0, 36)
    for button in (
        window.titleBar.minBtn,
        window.titleBar.maxBtn,
        window.titleBar.closeBtn,
    ):
        button.setNormalColor(icon_color)
        button.setHoverColor(icon_color)
        button.setPressedColor(icon_color)
        button.setHoverBackgroundColor(hover_bg)
        button.setPressedBackgroundColor(pressed_bg)
    offscreen_background = ""
    if QApplication.platformName() == "offscreen":
        palette = window.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#181818"))
        window.setPalette(palette)
        window.setAutoFillBackground(True)
        offscreen_background = """
        QWidget#LauncherWindow {
            background-color: rgb(24, 24, 24);
        }
        """
    else:
        window.setAutoFillBackground(False)
    window.titleBar.setStyleSheet("background-color: transparent; border: none;")
    window.view.setStyleSheet(
        offscreen_background
        + build_installer_surface_style_sheet()
        + """
        QWidget#OnboardingRoot,
        QWidget#OnboardingSurface,
        QFrame#OnboardingContentPanel {
            background-color: transparent;
            border: none;
        }
        QFrame#OnboardingIdentityRail {
            background-color: transparent;
            border: none;
        }
        QFrame#OnboardingHeroBadge {
            background-color: rgba(__ACCENT_RGB__, 0.12);
            border: 1px solid rgba(__ACCENT_RGB__, 0.24);
            border-radius: 14px;
        }
        QScrollArea#OnboardingPageStage,
        QWidget#OnboardingPageScrollContent,
        QWidget#OnboardingContentColumn,
        QFrame#OnboardingPageFrame,
        QFrame#OnboardingHeroPanel,
        QFrame#OnboardingFieldBlock,
        QFrame#OnboardingFooterRow {
            background-color: transparent;
            border: none;
        }
        QFrame#OnboardingSectionPanel {
            background-color: rgba(__WASH_RGB__, 0.04);
            border: 1px solid rgba(__WASH_RGB__, 0.075);
            border-radius: 22px;
        }
        QFrame#OnboardingStatusPanel {
            background-color: rgba(__WASH_RGB__, 0.035);
            border: 1px solid rgba(__WASH_RGB__, 0.065);
            border-radius: 18px;
        }
        QFrame#ExperiencePage,
        QWidget#ModelGallery,
        QScrollArea#ModelGalleryScroll,
        QFrame#ExperienceOptionGrid {
            background-color: transparent;
            border: none;
        }
QFrame#PreservationPanel {
            background-color: rgba(__ACCENT_RGB__, 0.075);
            border: 1px solid rgba(__ACCENT_RGB__, 0.18);
            border-radius: 16px;
}
QFrame#RepairScopeOption {
    background: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 10px;
}
QLabel#RepairScopeBadge {
    color: #ff4d8d;
}
        QRadioButton#RepairScopeChoice {
            background-color: rgba(__WASH_RGB__, 0.035);
            border: 1px solid rgba(__WASH_RGB__, 0.085);
            border-radius: 16px;
            padding: 12px 16px;
            spacing: 12px;
        }
        QRadioButton#RepairScopeChoice:checked {
            background-color: rgba(__ACCENT_RGB__, 0.09);
            border: 1px solid rgba(__ACCENT_RGB__, 0.42);
        }
        QFrame#ModelDiscoveryCard {
            background-color: rgba(__WASH_RGB__, 0.04);
            border: 1px solid rgba(__WASH_RGB__, 0.09);
            border-radius: 18px;
            min-width: 210px;
            max-width: 280px;
        }
        QLabel#ModelCardThumbnail {
            background-color: rgba(__ACCENT_RGB__, 0.12);
            border: 1px solid rgba(__ACCENT_RGB__, 0.18);
            border-radius: 12px;
            color: rgba(__ACCENT_RGB__, 0.95);
            font-size: 15px;
            font-weight: 650;
        }
        CaptionLabel#ModelCardDestination,
        CaptionLabel#ExperiencePageDescription,
        CaptionLabel#RepairStatus {
            color: rgba(__TEXT_RGB__, 0.72);
        }
        CaptionLabel#OnboardingPageDescription,
        CaptionLabel#OnboardingFieldHelper {
            color: rgba(__TEXT_RGB__, 0.74);
        }
        CaptionLabel#OnboardingHeroEyebrow,
        CaptionLabel#OnboardingFieldLabel {
            color: rgba(__ACCENT_RGB__, 0.9);
            font-weight: 600;
            text-transform: uppercase;
        }
        BodyLabel#OnboardingPageTitle {
            font-size: 22px;
            font-weight: 600;
        }
        BodyLabel#OnboardingOutputTitle {
            color: rgba(__TEXT_RGB__, 0.9);
            font-size: 16px;
            font-weight: 600;
        }
        CaptionLabel#OnboardingFieldLabel {
            font-size: 12px;
        }
        """.replace("__ACCENT_RGB__", accent_rgb)
        .replace("__TEXT_RGB__", text_rgb)
        .replace("__WASH_RGB__", wash_rgb)
    )
