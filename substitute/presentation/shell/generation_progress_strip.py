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

"""Render shared stacked progress bars for generation surfaces."""

from __future__ import annotations

from typing import Protocol, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import ProgressBar  # type: ignore[import-untyped]

try:
    from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
        isDarkTheme,
        themeColor,
    )
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True

    def themeColor() -> QColor:
        """Return a stable accent color for lightweight test stubs."""

        return QColor(0, 159, 170, 255)


from substitute.presentation.shell.chrome_style import connect_theme_refresh
from substitute.presentation.shell.progress_projection import (
    ProgressProjectionMode,
    set_progress_bar_value,
)


class ProgressViewStateLike(Protocol):
    """Describe progress view state consumed by generation progress strips."""

    @property
    def show_overlay(self) -> bool:
        """Return whether progress should be visible for active surfaces."""
        ...

    @property
    def workflow_value(self) -> int:
        """Return projected workflow progress."""
        ...

    @property
    def sampler_value(self) -> int:
        """Return projected sampler progress."""
        ...


class GenerationProgressStrip(QWidget):
    """Render stacked workflow and sampler generation progress bars."""

    strip_height = 6
    bar_height = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a transparent two-bar progress strip."""

        super().__init__(parent)
        self._progress_active = False
        self._locally_visible = False
        mouse_transparent_attribute = getattr(
            Qt.WidgetAttribute,
            "WA_TransparentForMouseEvents",
            None,
        )
        if mouse_transparent_attribute is None:
            mouse_transparent_attribute = getattr(Qt, "WA_TransparentForMouseEvents")
        self.setAttribute(cast(Qt.WidgetAttribute, mouse_transparent_attribute))
        self.setStyleSheet("background: transparent;")
        self.setFixedHeight(self.strip_height)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.workflow_bar = self._create_bar("Workflow: %p%")
        self.sampler_bar = self._create_bar("Sampler: %p%")
        layout.addWidget(self.workflow_bar)
        layout.addWidget(self.sampler_bar)

        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)
        self.hide()

    def apply_progress_view(
        self,
        view_state: ProgressViewStateLike,
        *,
        mode: ProgressProjectionMode = ProgressProjectionMode.LIVE_UPDATE,
    ) -> None:
        """Apply already-projected generation progress state."""

        self._progress_active = bool(view_state.show_overlay)
        self.set_progress_values(
            int(view_state.workflow_value),
            int(view_state.sampler_value),
            mode=mode,
        )
        self._sync_visibility()

    def set_progress_visible(self, visible: bool) -> None:
        """Set the local visibility gate for this progress strip."""

        self._locally_visible = visible
        self._sync_visibility()

    def set_progress_active(self, active: bool) -> None:
        """Set whether projected progress currently allows the strip to show."""

        self._progress_active = active
        self._sync_visibility()

    def set_progress_values(
        self,
        workflow_value: int,
        sampler_value: int,
        *,
        mode: ProgressProjectionMode = ProgressProjectionMode.LIVE_UPDATE,
    ) -> None:
        """Set workflow and sampler progress bar values."""

        set_progress_bar_value(
            self.workflow_bar,
            max(0, min(100, workflow_value)),
            mode=mode,
        )
        set_progress_bar_value(
            self.sampler_bar,
            max(0, min(100, sampler_value)),
            mode=mode,
        )

    def _create_bar(self, text_format: str) -> ProgressBar:
        """Create one transparent qfluent progress bar."""

        bar = ProgressBar(self)
        bar.setMaximum(100)
        bar.setMinimum(0)
        bar.setValue(0)
        bar.setFormat(text_format)
        bar.setFixedHeight(self.bar_height)
        bar.setCustomBackgroundColor(
            QColor(0, 0, 0, 0),
            QColor(0, 0, 0, 0),
        )
        return bar

    def _sync_visibility(self) -> None:
        """Show only when progress is active and the owner gate allows it."""

        if self._progress_active and self._locally_visible:
            self.show()
            return
        self.hide()

    def _apply_theme_styles(self) -> None:
        """Apply theme-aware progress colors shared by all generation strips."""

        accent = themeColor()
        accent_name = getattr(accent, "name", None)
        accent_color = accent_name() if callable(accent_name) else "#09f"
        sampler_color = "#F59E0B" if isDarkTheme() else "#C56A00"
        self.workflow_bar.setStyleSheet(self._bar_stylesheet(accent_color))
        self.sampler_bar.setStyleSheet(self._bar_stylesheet(sampler_color))

    @staticmethod
    def _bar_stylesheet(chunk_color: str) -> str:
        """Return the compact two-pixel progress bar stylesheet."""

        return f"""
            QProgressBar {{
                border-radius: 2px;
                min-height: 2px;
                max-height: 2px;
                padding: 0px;
                background: transparent;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {chunk_color};
                border-radius: 2px;
                margin: 0px;
            }}
            """


__all__ = ["GenerationProgressStrip", "ProgressViewStateLike"]
