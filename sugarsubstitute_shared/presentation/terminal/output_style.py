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

"""Provide shared styling and font helpers for terminal-style output surfaces."""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase

try:
    from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
        isDarkTheme,
        themeColor,
    )
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True

    def themeColor() -> object:
        """Return a stable accent color for lightweight test stubs."""

        from PySide6.QtGui import QColor

        return QColor("#009faa")


_TERMINAL_FONT_FALLBACKS = (
    "Cascadia Mono",
    "Cascadia Code",
    "Consolas",
    "Menlo",
    "Monaco",
    "Liberation Mono",
    "DejaVu Sans Mono",
    "Noto Sans Mono",
    "Courier New",
)


def create_terminal_output_font(*, point_size: int = 9) -> QFont:
    """Return the shared monospace font used by terminal-style views."""

    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    system_family = font.family().strip()
    font_families = [
        family for family in (system_family, *_TERMINAL_FONT_FALLBACKS) if family
    ]
    font.setFamilies(list(dict.fromkeys(font_families)))
    font.setStyleHint(QFont.StyleHint.TypeWriter)
    font.setFixedPitch(True)
    font.setPointSize(point_size)
    return font


def build_terminal_output_stylesheet() -> str:
    """Return the shared terminal surface stylesheet used across the app."""

    if isDarkTheme():
        return """
        QFrame#TerminalOutputView {
            background-color: rgba(8, 10, 12, 0.97);
            border: 1px solid rgba(255, 255, 255, 0.22);
            border-bottom: 1px solid rgba(255, 255, 255, 0.44);
            border-radius: 6px;
        }
    """
    return """
        QFrame#TerminalOutputView {
            background-color: rgba(252, 253, 255, 0.96);
            border: 1px solid rgba(0, 0, 0, 0.16);
            border-bottom: 1px solid rgba(0, 0, 0, 0.24);
            border-radius: 6px;
        }
    """


def build_terminal_output_log_stylesheet() -> str:
    """Return the direct stylesheet used by the visible terminal text widget."""

    accent = themeColor()
    accent_rgb = f"{accent.red()}, {accent.green()}, {accent.blue()}"
    text_color = (
        "rgba(230, 236, 241, 0.92)" if isDarkTheme() else "rgba(30, 35, 40, 0.95)"
    )
    selection_color = (
        "rgba(255, 255, 255, 0.98)" if isDarkTheme() else "rgba(255, 255, 255, 0.98)"
    )
    return f"""
        PlainTextEdit#TerminalOutputLog,
        QPlainTextEdit#TerminalOutputLog {{
            background-color: transparent;
            border: none;
            padding: 0px 10px;
            color: {text_color};
            selection-background-color: rgba({accent_rgb}, 0.42);
            selection-color: {selection_color};
        }}
        QWidget#TerminalOutputViewport {{
            background-color: transparent;
        }}
    """


__all__ = [
    "build_terminal_output_log_stylesheet",
    "build_terminal_output_stylesheet",
    "create_terminal_output_font",
]
