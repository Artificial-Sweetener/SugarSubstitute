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

"""Own the visual contract shared by every installer process."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPaintEvent, QPainter
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
    themeColor,
)

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import render_application_text


INSTALLER_WINDOW_WIDTH = 1180
INSTALLER_WINDOW_HEIGHT = 760
INSTALLER_BRAND_BAR_HEIGHT = 126
INSTALLER_CONTENT_MAX_WIDTH = 1030
INSTALLER_WORDMARK_WIDTH = 270
INSTALLER_WORDMARK_HEIGHT = 88
INSTALLER_WORDMARK_OPTICAL_Y_OFFSET = 2


def configure_installer_title_bar(title_bar: QWidget) -> None:
    """Keep native controls in the top edge of the full-height drag region."""

    title_bar.setFixedHeight(INSTALLER_BRAND_BAR_HEIGHT)
    layout = title_bar.layout()
    if layout is None:
        raise RuntimeError("Installer title bar requires a layout")
    layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)


def expose_native_material(widget: QWidget) -> None:
    """Keep one installer surface from painting over its native backdrop."""

    widget.setAutoFillBackground(False)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)


def installer_wordmark_path() -> Path:
    """Return the README wordmark from source or a frozen launcher bundle."""

    packaged_path = (
        Path(getattr(sys, "_MEIPASS", ""))
        / "launcher_assets"
        / "sugarsubstitute-logo.svg"
    )
    if packaged_path.is_file():
        return packaged_path

    source_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "readme"
        / "sugarsubstitute-logo.svg"
    )
    if source_path.is_file():
        return source_path
    raise FileNotFoundError(f"Installer wordmark is missing: {source_path}")


def center_installer_window(window: QWidget) -> bool:
    """Center a fresh installer window within its assigned screen work area."""

    screen = window.screen()
    if screen is None:
        return False
    frame_center = window.frameGeometry().center()
    target_center = screen.availableGeometry().center()
    window.move(window.pos() + target_center - frame_center)
    return True


class InstallerBrandBar(QFrame):
    """Render the persistent wordmark and compact journey progress."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the Mica-revealing top bar used across process handoff."""

        super().__init__(parent)
        self.setObjectName("InstallerBrandBar")
        self.setFixedHeight(INSTALLER_BRAND_BAR_HEIGHT)
        expose_native_material(self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(38, 19, 52, 19)
        layout.setSpacing(24)

        self.wordmark_host = QWidget(self)
        self.wordmark_host.setObjectName("InstallerWordmarkHost")
        self.wordmark_host.setFixedSize(
            INSTALLER_WORDMARK_WIDTH,
            INSTALLER_WORDMARK_HEIGHT,
        )
        expose_native_material(self.wordmark_host)
        self.wordmark = QSvgWidget(
            str(installer_wordmark_path()),
            self.wordmark_host,
        )
        self.wordmark.setObjectName("InstallerWordmark")
        self.wordmark.setGeometry(
            0,
            INSTALLER_WORDMARK_OPTICAL_Y_OFFSET,
            INSTALLER_WORDMARK_WIDTH,
            INSTALLER_WORDMARK_HEIGHT,
        )
        self.wordmark.setAccessibleName(
            render_application_text(app_text("SugarSubstitute"))
        )
        layout.addWidget(self.wordmark_host, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)

        progress_host = QWidget(self)
        progress_host.setObjectName("InstallerProgressHost")
        progress_host.setFixedSize(220, 44)
        progress_layout = QVBoxLayout(progress_host)
        progress_layout.setContentsMargins(0, 6, 0, 6)
        progress_layout.setSpacing(5)
        self.progress_caption = QLabel(self)
        self.progress_caption.setObjectName("InstallerStepLabel")
        self.progress_caption.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        progress_layout.addWidget(self.progress_caption)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("InstallerJourneyProgress")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedSize(220, 4)
        self.progress_bar.setRange(0, 4)
        self.progress_bar.setValue(1)
        progress_layout.addWidget(self.progress_bar)
        layout.addWidget(progress_host, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_progress(self, *, current: int, total: int, description: str) -> None:
        """Project compact semantic progress without adding another text block."""

        self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setValue(max(0, min(current, total)))
        self.progress_bar.setAccessibleName(description)
        self.progress_caption.setText(description)


class InstallerBodyMaterialSurface(QWidget):
    """Paint the installer body wash while leaving its brand bar on native Mica."""

    def __init__(self, *, object_name: str, parent: QWidget) -> None:
        """Create the single body-wash owner used by both installer processes."""

        super().__init__(parent)
        self.setObjectName(object_name)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint the same translucent body wash used by the main application."""

        _ = event
        painter = QPainter(self)
        wash = QColor(32, 32, 32, 150) if isDarkTheme() else QColor(251, 251, 251, 188)
        painter.fillRect(self.rect(), wash)
        border = QColor(255, 255, 255, 18) if isDarkTheme() else QColor(0, 0, 0, 18)
        painter.fillRect(0, 0, self.width(), 1, border)


def build_installer_surface_style_sheet() -> str:
    """Return shared Mica Alt layering and installer geometry styles."""

    accent = themeColor()
    accent_rgb = f"{accent.red()}, {accent.green()}, {accent.blue()}"
    text_rgb = "255, 255, 255" if isDarkTheme() else "0, 0, 0"
    card_rgb = "255, 255, 255" if isDarkTheme() else "255, 255, 255"
    card_alpha = "12" if isDarkTheme() else "170"
    border_rgb = "255, 255, 255" if isDarkTheme() else "0, 0, 0"
    return (
        """
        AcrylicWindow,
        QWidget#LauncherWindow,
        QWidget#OnboardingWindow {
            background: transparent;
            border: none;
        }
        QFrame#InstallerBrandBar {
            background: transparent;
            border: none;
        }
        QWidget#InstallerWordmarkHost,
        QSvgWidget#InstallerWordmark {
            background: transparent;
            border: none;
        }
        QWidget#InstallerProgressHost {
            background: transparent;
            border: none;
        }
        QScrollArea#OnboardingPageStage,
        QScrollArea#OnboardingPageStage > QWidget > QWidget,
        QWidget#OnboardingPageScrollContent {
            background: transparent;
            border: none;
        }
        QScrollBar:vertical {
            background: transparent;
            border: none;
            margin: 0;
            width: 8px;
        }
        QScrollBar::handle:vertical {
            background-color: rgba(__BORDER_RGB__, 42);
            border: none;
            border-radius: 4px;
            min-height: 36px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: rgba(__BORDER_RGB__, 68);
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0;
        }
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {
            background: transparent;
        }
        QFrame#InstallerContentWash,
        QFrame#OnboardingContentPanel {
            background: transparent;
            border: none;
        }
        QProgressBar#InstallerJourneyProgress {
            background-color: rgba(__BORDER_RGB__, 30);
            border: none;
            border-radius: 2px;
        }
        QProgressBar#InstallerJourneyProgress::chunk {
            background-color: rgb(__ACCENT_RGB__);
            border-radius: 2px;
        }
        QFrame#OnboardingSectionPanel,
        QFrame#OnboardingStatusPanel,
        QFrame#OnboardingInfoPanel,
        QFrame#ManagedRuntimeSummaryPanel,
        QFrame#OnboardingModeSummaryPanel {
            background-color: rgba(__CARD_RGB__, __CARD_ALPHA__);
            border: 1px solid rgba(__BORDER_RGB__, 20);
        }
        QLabel#InstallerStepLabel {
            color: rgba(__TEXT_RGB__, 150);
            font-weight: 600;
        }
        """.replace("__ACCENT_RGB__", accent_rgb)
        .replace("__TEXT_RGB__", text_rgb)
        .replace("__CARD_RGB__", card_rgb)
        .replace("__CARD_ALPHA__", card_alpha)
        .replace("__BORDER_RGB__", border_rgb)
    )


__all__ = [
    "INSTALLER_BRAND_BAR_HEIGHT",
    "INSTALLER_CONTENT_MAX_WIDTH",
    "INSTALLER_WORDMARK_HEIGHT",
    "INSTALLER_WORDMARK_OPTICAL_Y_OFFSET",
    "INSTALLER_WORDMARK_WIDTH",
    "INSTALLER_WINDOW_HEIGHT",
    "INSTALLER_WINDOW_WIDTH",
    "InstallerBrandBar",
    "InstallerBodyMaterialSurface",
    "build_installer_surface_style_sheet",
    "center_installer_window",
    "configure_installer_title_bar",
    "expose_native_material",
    "installer_wordmark_path",
]
