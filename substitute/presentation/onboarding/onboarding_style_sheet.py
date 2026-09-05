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

"""Build the onboarding shell's theme-aware QSS stylesheet."""

from __future__ import annotations

from PySide6.QtGui import QColor
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
    themeColor,
)


def build_onboarding_style_sheet() -> str:
    """Return onboarding QSS for the active Fluent theme and accent."""

    accent = themeColor()
    accent_rgb = f"{accent.red()}, {accent.green()}, {accent.blue()}"
    warning = QColor("#F5A524")
    warning_rgb = f"{warning.red()}, {warning.green()}, {warning.blue()}"
    wash_rgb = "255, 255, 255" if isDarkTheme() else "0, 0, 0"
    text_rgb = "255, 255, 255" if isDarkTheme() else "0, 0, 0"
    return (
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
        QFrame#OnboardingHeroBadge,
        QFrame#OnboardingTargetCardBadge,
        QFrame#OnboardingCompletionBadge {
            background-color: rgba(__ACCENT_RGB__, 0.12);
            border: 1px solid rgba(__ACCENT_RGB__, 0.24);
            border-radius: 14px;
        }
        QFrame#OnboardingIssuePanel {
            background-color: rgba(__WARNING_RGB__, 0.10);
            border: 1px solid rgba(__WARNING_RGB__, 0.28);
            border-radius: 16px;
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
        QFrame#OnboardingPageFrame,
        QWidget#OnboardingContentColumn {
            background-color: transparent;
            border: none;
        }
        QFrame#OnboardingSectionPanel {
            background-color: rgba(__WASH_RGB__, 0.04);
            border: 1px solid rgba(__WASH_RGB__, 0.075);
            border-radius: 22px;
        }
        QFrame#OnboardingInfoPanel,
        QFrame#OnboardingModeSummaryPanel,
        QFrame#ManagedRuntimeSummaryPanel,
        QFrame#OnboardingStatusPanel {
            background-color: rgba(__WASH_RGB__, 0.035);
            border: 1px solid rgba(__WASH_RGB__, 0.065);
            border-radius: 18px;
        }
        QFrame#OnboardingLogSurface,
        QFrame#OnboardingCommandSurface {
            background-color: transparent;
            border: none;
            border-radius: 0px;
        }
        QFrame#OnboardingCompletionSurface {
            background-color: rgba(__WASH_RGB__, 0.025);
            border: none;
            border-radius: 18px;
        }
        QFrame#OnboardingTargetCard {
            background-color: rgba(__WASH_RGB__, 0.025);
            border: 1px solid rgba(__WASH_RGB__, 0.055);
            border-radius: 18px;
        }
        QFrame#OnboardingTargetCard[selected="true"] {
            background-color: rgba(__ACCENT_RGB__, 0.09);
            border: 1px solid rgba(__ACCENT_RGB__, 0.26);
        }
        QFrame#OnboardingRecommendationCard {
            background-color: rgba(__WASH_RGB__, 0.028);
            border: 1px solid rgba(__WASH_RGB__, 0.07);
            border-radius: 18px;
        }
        QFrame#OnboardingRecommendationCard[selected="true"] {
            background-color: rgba(__ACCENT_RGB__, 0.10);
            border: 2px solid rgba(__ACCENT_RGB__, 0.72);
        }
        QFrame#OnboardingDownloadReviewGroup {
            background-color: rgba(__WASH_RGB__, 0.028);
            border: 1px solid rgba(__WASH_RGB__, 0.07);
            border-radius: 18px;
        }
        QFrame#OnboardingDownloadReviewItem {
            background-color: rgba(__WASH_RGB__, 0.035);
            border: 1px solid rgba(__WASH_RGB__, 0.055);
            border-radius: 12px;
        }
        QFrame#OnboardingDownloadSummaryPanel {
            background-color: rgba(__ACCENT_RGB__, 0.08);
            border: 1px solid rgba(__ACCENT_RGB__, 0.22);
            border-radius: 16px;
        }
        BodyLabel#OnboardingRailTitle {
            font-size: 24px;
            font-weight: 600;
        }
        CaptionLabel#OnboardingRailSummary,
        CaptionLabel#OnboardingProgressHelper,
        CaptionLabel#OnboardingIssueBody,
        CaptionLabel#OnboardingIssueDetail,
        CaptionLabel#OnboardingPageDescription,
        CaptionLabel#OnboardingFieldHelper,
        CaptionLabel#OnboardingInfoDescription,
        CaptionLabel#OnboardingInfoDetail,
        CaptionLabel#OnboardingModeSummaryText,
        CaptionLabel#OnboardingModeTechnicalNote,
        CaptionLabel#OnboardingTargetCardSummary,
        CaptionLabel#OnboardingTargetCardBestIf,
        CaptionLabel#OnboardingStatusDetail,
        CaptionLabel#OnboardingCompletionSummary,
        CaptionLabel#OnboardingSectionSupport {
            color: rgba(__TEXT_RGB__, 0.74);
        }
        CaptionLabel#OnboardingDownloadReviewFileName,
        CaptionLabel#OnboardingDownloadDestination,
        CaptionLabel#OnboardingDownloadSummaryLabel {
            color: rgba(__TEXT_RGB__, 0.66);
        }
        CaptionLabel#OnboardingHeroEyebrow,
        CaptionLabel#OnboardingFieldLabel,
        CaptionLabel#OnboardingProgressCount {
            color: rgba(__ACCENT_RGB__, 0.9);
            font-weight: 600;
            text-transform: uppercase;
        }
        CaptionLabel#OnboardingDownloadReviewGroupTitle {
            color: rgba(__ACCENT_RGB__, 0.9);
            font-weight: 600;
            text-transform: uppercase;
        }
        BodyLabel#OnboardingPageTitle,
        BodyLabel#OnboardingProgressTitle,
        BodyLabel#OnboardingIssueTitle,
        BodyLabel#OnboardingInfoTitle,
        BodyLabel#OnboardingTargetCardTitle {
            font-size: 22px;
            font-weight: 600;
        }
        BodyLabel#OnboardingTargetCardTitle,
        BodyLabel#OnboardingIssueTitle {
            font-size: 18px;
        }
        BodyLabel#OnboardingDownloadReviewItemTitle,
        BodyLabel#OnboardingDownloadReviewItemSize {
            font-size: 15px;
            font-weight: 600;
        }
        BodyLabel#OnboardingDownloadSummaryValue {
            font-size: 20px;
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
        BodyLabel#OnboardingProgressStatus {
            font-size: 24px;
            font-weight: 600;
        }
        BodyLabel#OnboardingOutputTitle {
            color: rgba(__TEXT_RGB__, 0.9);
            font-size: 16px;
            font-weight: 600;
        }
        QFrame#OnboardingFooterRow,
        QFrame#OnboardingHeroPanel,
        QFrame#OnboardingFieldBlock {
            background-color: transparent;
            border: none;
        }
        QPushButton[binarySelected="true"] {
            background-color: rgba(__ACCENT_RGB__, 0.24);
            border: 1px solid rgba(__ACCENT_RGB__, 0.72);
        }
        BodyLabel#OnboardingCommandLabel {
            font-family: Consolas, 'Courier New', monospace;
            font-size: 13px;
        }
        """.replace("__ACCENT_RGB__", accent_rgb)
        .replace("__WARNING_RGB__", warning_rgb)
        .replace("__WASH_RGB__", wash_rgb)
        .replace("__TEXT_RGB__", text_rgb)
    )


__all__ = ["build_onboarding_style_sheet"]
