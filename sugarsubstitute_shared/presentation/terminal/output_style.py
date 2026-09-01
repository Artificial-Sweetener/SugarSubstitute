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

from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont, QFontDatabase


_TERMINAL_FONT_FALLBACKS = (
    "Cascadia Mono",
    "Cascadia Code",
    "Consolas",
    "Menlo",
    "Monaco",
    "Liberation Mono",
    "DejaVu Sans Mono",
    "Noto Sans Mono",
    "Noto Sans Mono CJK SC",
    "Noto Sans Mono CJK JP",
    "Microsoft YaHei UI",
    "Yu Gothic UI",
    "Courier New",
)


@dataclass(frozen=True, slots=True)
class TerminalOutputAppearance:
    """Describe theme inputs needed to paint a terminal output surface."""

    dark_theme: bool
    accent_red: int
    accent_green: int
    accent_blue: int

    @classmethod
    def from_color(
        cls,
        *,
        dark_theme: bool,
        accent_color: str,
    ) -> TerminalOutputAppearance:
        """Build a validated terminal appearance from an RGB color string."""

        color = QColor(accent_color)
        if not color.isValid():
            raise ValueError("Terminal accent color must be a valid Qt color.")
        return cls(
            dark_theme=dark_theme,
            accent_red=color.red(),
            accent_green=color.green(),
            accent_blue=color.blue(),
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


def build_terminal_output_stylesheet(
    appearance: TerminalOutputAppearance | None = None,
) -> str:
    """Return the shared terminal surface stylesheet used across the app."""

    resolved = appearance or _qfluent_output_appearance()
    if resolved.dark_theme:
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


def build_terminal_output_log_stylesheet(
    appearance: TerminalOutputAppearance | None = None,
) -> str:
    """Return the direct stylesheet used by the visible terminal text widget."""

    resolved = appearance or _qfluent_output_appearance()
    accent_rgb = (
        f"{resolved.accent_red}, {resolved.accent_green}, {resolved.accent_blue}"
    )
    text_color = (
        "rgba(230, 236, 241, 0.92)" if resolved.dark_theme else "rgba(30, 35, 40, 0.95)"
    )
    selection_color = "rgba(255, 255, 255, 0.98)"
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


def _qfluent_output_appearance() -> TerminalOutputAppearance:
    """Resolve live QFluent colors only for normal application terminal views."""

    try:
        from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
            isDarkTheme,
            themeColor,
        )
    except ImportError:  # pragma: no cover - lightweight test stubs
        return TerminalOutputAppearance.from_color(
            dark_theme=True,
            accent_color="#009FAA",
        )
    accent = themeColor()
    return TerminalOutputAppearance(
        dark_theme=bool(isDarkTheme()),
        accent_red=int(accent.red()),
        accent_green=int(accent.green()),
        accent_blue=int(accent.blue()),
    )


__all__ = [
    "build_terminal_output_log_stylesheet",
    "build_terminal_output_stylesheet",
    "create_terminal_output_font",
    "TerminalOutputAppearance",
]
