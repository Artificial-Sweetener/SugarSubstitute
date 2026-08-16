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
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
    themeColor,
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
    window.titleBar.setStyleSheet("background-color: transparent; border: none;")
    window.setStyleSheet(
        """
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
        QFrame#OnboardingIconBadge,
        QFrame#OnboardingHeroBadge {
            background-color: rgba(__ACCENT_RGB__, 0.12);
            border: 1px solid rgba(__ACCENT_RGB__, 0.24);
            border-radius: 14px;
        }
        QFrame#OnboardingStepItem {
            background-color: transparent;
            border: none;
            border-radius: 14px;
        }
        QFrame#OnboardingStepItem[stepState="active"] {
            background-color: rgba(__WASH_RGB__, 0.045);
            border: 1px solid rgba(__WASH_RGB__, 0.075);
        }
        QFrame#OnboardingStepItem[stepState="complete"] {
            background-color: transparent;
            border: none;
        }
        QWidget#OnboardingPageStage,
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
        BodyLabel#OnboardingRailTitle {
            font-size: 24px;
            font-weight: 600;
        }
        CaptionLabel#OnboardingRailSummary,
        CaptionLabel#OnboardingProgressHelper,
        CaptionLabel#OnboardingPageDescription,
        CaptionLabel#OnboardingFieldHelper {
            color: rgba(__TEXT_RGB__, 0.74);
        }
        CaptionLabel#OnboardingHeroEyebrow,
        CaptionLabel#OnboardingFieldLabel,
        CaptionLabel#OnboardingProgressCount {
            color: rgba(__ACCENT_RGB__, 0.9);
            font-weight: 600;
            text-transform: uppercase;
        }
        BodyLabel#OnboardingPageTitle,
        BodyLabel#OnboardingProgressTitle {
            font-size: 22px;
            font-weight: 600;
        }
        BodyLabel#OnboardingStepNumber {
            min-width: 24px;
            max-width: 24px;
            min-height: 24px;
            max-height: 24px;
            border-radius: 12px;
            qproperty-alignment: 'AlignCenter';
            background-color: rgba(__WASH_RGB__, 0.06);
            color: rgba(__TEXT_RGB__, 0.68);
            font-size: 12px;
            font-weight: 700;
        }
        BodyLabel#OnboardingStepNumber[stepState="active"] {
            background-color: rgba(__ACCENT_RGB__, 0.32);
            color: rgba(__TEXT_RGB__, 1.0);
        }
        BodyLabel#OnboardingStepNumber[stepState="complete"] {
            background-color: rgba(__ACCENT_RGB__, 0.18);
            color: rgba(__TEXT_RGB__, 0.92);
        }
        CaptionLabel#OnboardingStepTitle {
            color: rgba(__TEXT_RGB__, 0.62);
        }
        CaptionLabel#OnboardingStepTitle[stepState="active"] {
            color: rgba(__TEXT_RGB__, 0.98);
            font-weight: 600;
        }
        CaptionLabel#OnboardingStepTitle[stepState="complete"] {
            color: rgba(__TEXT_RGB__, 0.78);
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
