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
    dialog_rgb = "30, 30, 30" if isDarkTheme() else "249, 249, 249"
    return (
        """
        QWidget#OnboardingRoot,
        QWidget#OnboardingSurface,
        QFrame#OnboardingContentPanel {
            background-color: transparent;
            border: none;
        }
        QDialog#OnboardingConnectionSettingsDialog,
        QDialog#OnboardingSetupLogDialog {
            background-color: rgb(__DIALOG_RGB__);
        }
        QFrame#OnboardingIdentityRail {
            background-color: transparent;
            border: none;
        }
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
        QFrame#OnboardingRecommendationLoadingCard {
            background-color: rgba(__WASH_RGB__, 0.022);
            border: 1px solid rgba(__WASH_RGB__, 0.055);
            border-radius: 18px;
        }
        QFrame#OnboardingRecommendationLoadingPortrait {
            background-color: rgba(__WASH_RGB__, 0.045);
            border: 1px solid rgba(__WASH_RGB__, 0.055);
            border-radius: 14px;
        }
        QFrame#OnboardingRecommendationLoadingAction {
            background-color: rgba(__WASH_RGB__, 0.045);
            border: none;
            border-radius: 6px;
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
        QFrame#OnboardingDownloadCartCard {
            background-color: rgba(__WASH_RGB__, 0.028);
            border: 1px solid rgba(__WASH_RGB__, 0.07);
            border-radius: 18px;
        }
        QFrame#OnboardingDownloadSummaryPanel {
            background-color: rgba(__ACCENT_RGB__, 0.08);
            border: 1px solid rgba(__ACCENT_RGB__, 0.22);
            border-radius: 16px;
        }
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
        CaptionLabel#OnboardingFieldLabel {
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
        BodyLabel#OnboardingDialogTitle,
        BodyLabel#OnboardingIssueTitle,
        BodyLabel#OnboardingInfoTitle,
        BodyLabel#OnboardingTargetCardTitle {
            font-size: 22px;
            font-weight: 600;
        }
        BodyLabel#OnboardingDialogTitle {
            font-size: 24px;
        }
        BodyLabel#OnboardingTargetCardTitle,
        BodyLabel#OnboardingIssueTitle {
            font-size: 18px;
        }
        BodyLabel#OnboardingDownloadReviewItemTitle,
        BodyLabel#OnboardingDownloadReviewItemSize,
        BodyLabel#OnboardingDownloadCartSize {
            font-size: 15px;
            font-weight: 600;
        }
        BodyLabel#OnboardingDownloadSummaryValue {
            font-size: 20px;
            font-weight: 600;
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
        .replace("__DIALOG_RGB__", dialog_rgb)
    )


__all__ = ["build_onboarding_style_sheet"]
