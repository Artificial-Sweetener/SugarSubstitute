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

"""Render the shell-owned Comfy output panel around the shared terminal view."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    FluentIcon as FIF,
    PlainTextEdit,
    TransparentToolButton,
)

from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from sugarsubstitute_shared.presentation.terminal.output_view import TerminalOutputView
from substitute.presentation.shell.chrome_style import connect_theme_refresh

try:
    from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True


class ComfyOutputPanel(QFrame):
    """Show buffered Comfy output in a wrapped, shell-integrated bottom panel."""

    _UNBOUNDED_MAX_HEIGHT = 16777215

    def __init__(
        self, parent: QFrame | None = None, *, panel_height: int = 200
    ) -> None:
        """Build the shell panel frame around the shared terminal surface."""

        super().__init__(parent)
        self._preferred_height = panel_height
        self._minimum_visible_height = 120

        self.setObjectName("ComfyOutputPanel")
        self.setMinimumHeight(self._minimum_visible_height)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(8)

        self._header = QWidget(self)
        self._header.setObjectName("ComfyOutputHeader")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self._title_label = BodyLabel("Comfy Console", self._header)
        self._title_label.setObjectName("ComfyOutputTitle")
        header_layout.addWidget(self._title_label)
        header_layout.addStretch(1)

        self._copy_button = TransparentToolButton(FIF.COPY, self._header)
        self._copy_button.setObjectName("ComfyOutputCopyButton")
        self._copy_button.setToolTip("Copy all output")
        self._copy_button.clicked.connect(self.copy_all_output)
        header_layout.addWidget(
            self._copy_button, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        self._clear_button = TransparentToolButton(FIF.BROOM, self._header)
        self._clear_button.setObjectName("ComfyOutputClearButton")
        self._clear_button.setToolTip("Clear output")
        self._clear_button.clicked.connect(self.clear_output)
        header_layout.addWidget(
            self._clear_button, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        root_layout.addWidget(self._header)

        self._terminal_view = TerminalOutputView(
            self,
        )
        self._terminal_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        root_layout.addWidget(self._terminal_view)

        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)

        self.set_panel_visible(False)

    @property
    def log_view(self) -> PlainTextEdit:
        """Return the wrapped log widget for characterization tests."""

        return self._terminal_view.log_view

    def set_stream(self, stream: TerminalOutputStream | None) -> None:
        """Bind this panel to one output stream and replay existing history."""

        self._terminal_view.set_stream(stream)

    def append_line(self, line: str) -> None:
        """Append one line to the log view and keep the viewport pinned low."""

        self._terminal_view.append_line(line)

    def clear_output(self) -> None:
        """Clear the visible log content only."""

        self._terminal_view.clear_output()

    def copy_all_output(self) -> None:
        """Copy the visible log contents to the system clipboard."""

        self._terminal_view.copy_all_output()

    def set_panel_visible(self, visible: bool) -> None:
        """Show or collapse the panel without leaving layout space."""

        if visible:
            self.setMinimumHeight(self._minimum_visible_height)
            self.setMaximumHeight(self._UNBOUNDED_MAX_HEIGHT)
            self.show()
            if self._host_splitter() is None:
                self.setFixedHeight(self._preferred_height)
                return
            self._restore_preferred_height()
            return

        self._remember_current_height()
        self.hide()
        if self._host_splitter() is None:
            self.setFixedHeight(0)
            return
        self._collapse_height()

    def is_panel_visible(self) -> bool:
        """Return whether the panel currently occupies layout space."""

        return self.isVisible() and self.height() > 0

    def _remember_current_height(self) -> None:
        """Persist the latest visible height so the splitter can restore it later."""

        if self.isVisible() and self.height() > 0:
            self._preferred_height = max(self.height(), self._minimum_visible_height)

    def _restore_preferred_height(self) -> None:
        """Restore the last panel height inside the owning vertical splitter."""

        splitter = self._host_splitter()
        if splitter is None:
            return
        sizes = splitter.sizes()
        total_height = sum(size for size in sizes if size > 0)
        if total_height <= 0:
            total_height = max(
                splitter.height(),
                self._preferred_height + self._minimum_visible_height,
            )
        panel_height = min(
            self._preferred_height,
            max(
                total_height - self._minimum_visible_height,
                self._minimum_visible_height,
            ),
        )
        top_height = max(total_height - panel_height, self._minimum_visible_height)
        splitter.setSizes([top_height, panel_height])

    def _collapse_height(self) -> None:
        """Collapse the panel row inside the owning vertical splitter."""

        splitter = self._host_splitter()
        if splitter is None:
            return
        sizes = splitter.sizes()
        total_height = sum(size for size in sizes if size > 0)
        if total_height <= 0:
            total_height = max(
                splitter.height(),
                self._preferred_height + self._minimum_visible_height,
            )
        splitter.setSizes([total_height, 0])

    def _host_splitter(self) -> QSplitter | None:
        """Return the owning vertical splitter when hosted inside one."""

        parent = self.parentWidget()
        if not isinstance(parent, QSplitter):
            return None
        return parent

    def _apply_theme_styles(self) -> None:
        """Reapply shell-owned header styles after theme or accent changes."""

        title_color = (
            "rgba(244, 247, 250, 0.94)" if isDarkTheme() else "rgba(26, 32, 38, 0.96)"
        )
        self.setStyleSheet(
            f"""
            QFrame#ComfyOutputPanel {{
                background: transparent;
                border: none;
            }}
            QWidget#ComfyOutputHeader {{
                background: transparent;
                border: none;
            }}
            BodyLabel#ComfyOutputTitle {{
                color: {title_color};
                font-size: 15px;
                font-weight: 600;
            }}
            """
        )


__all__ = ["ComfyOutputPanel"]
