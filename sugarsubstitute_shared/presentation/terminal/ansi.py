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

"""Parse ANSI SGR terminal styling into renderable text spans."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Final


@dataclass(frozen=True)
class TerminalTextSpan:
    """Describe one text run with terminal styling attributes."""

    text: str
    foreground: str | None = None
    bold: bool = False


@dataclass(frozen=True)
class TerminalStyledLine:
    """Describe one terminal line as plain text and styled text spans."""

    plain_text: str
    spans: tuple[TerminalTextSpan, ...]


@dataclass(frozen=True)
class _AnsiStyle:
    """Track active ANSI SGR attributes while parsing one record."""

    foreground: str | None = None
    bold: bool = False


_ANSI_ESCAPE_PATTERN: Final[re.Pattern[str]] = re.compile(r"\x1b\[(?P<codes>[0-9;]*)m")
_STANDARD_FOREGROUND_COLORS: Final[dict[int, str]] = {
    30: "black",
    31: "red",
    32: "green",
    33: "yellow",
    34: "blue",
    35: "magenta",
    36: "cyan",
    37: "white",
    90: "bright_black",
    91: "bright_red",
    92: "bright_green",
    93: "bright_yellow",
    94: "bright_blue",
    95: "bright_magenta",
    96: "bright_cyan",
    97: "bright_white",
}


def parse_ansi_sgr_record(record: str) -> TerminalStyledLine:
    """Return a styled line from one terminal record containing ANSI SGR codes."""

    spans: list[TerminalTextSpan] = []
    plain_parts: list[str] = []
    active_style = _AnsiStyle()
    cursor = 0
    for match in _ANSI_ESCAPE_PATTERN.finditer(record):
        if match.start() > cursor:
            text = record[cursor : match.start()]
            _append_span(spans, text, active_style)
            plain_parts.append(text)
        active_style = _style_after_sgr_codes(active_style, match.group("codes"))
        cursor = match.end()
    if cursor < len(record):
        text = record[cursor:]
        _append_span(spans, text, active_style)
        plain_parts.append(text)
    plain_text = "".join(plain_parts)
    return TerminalStyledLine(plain_text=plain_text, spans=tuple(spans))


def _append_span(
    spans: list[TerminalTextSpan],
    text: str,
    style: _AnsiStyle,
) -> None:
    """Append one non-empty span, merging adjacent runs with matching style."""

    if not text:
        return
    span = TerminalTextSpan(
        text=text,
        foreground=style.foreground,
        bold=style.bold,
    )
    if spans and _same_style(spans[-1], span):
        previous = spans[-1]
        spans[-1] = TerminalTextSpan(
            text=f"{previous.text}{span.text}",
            foreground=previous.foreground,
            bold=previous.bold,
        )
        return
    spans.append(span)


def _style_after_sgr_codes(style: _AnsiStyle, codes_text: str) -> _AnsiStyle:
    """Return the active style after applying one SGR code sequence."""

    codes = _parse_sgr_codes(codes_text)
    active = style
    for code in codes:
        if code == 0:
            active = _AnsiStyle()
        elif code == 1:
            active = _AnsiStyle(foreground=active.foreground, bold=True)
        elif code == 22:
            active = _AnsiStyle(foreground=active.foreground, bold=False)
        elif code == 39:
            active = _AnsiStyle(foreground=None, bold=active.bold)
        elif code in _STANDARD_FOREGROUND_COLORS:
            active = _AnsiStyle(
                foreground=_STANDARD_FOREGROUND_COLORS[code],
                bold=active.bold,
            )
    return active


def _parse_sgr_codes(codes_text: str) -> tuple[int, ...]:
    """Return integer SGR codes, treating an empty code as reset."""

    if not codes_text:
        return (0,)
    codes: list[int] = []
    for raw_code in codes_text.split(";"):
        try:
            codes.append(int(raw_code) if raw_code else 0)
        except ValueError:
            continue
    return tuple(codes) or (0,)


def _same_style(left: TerminalTextSpan, right: TerminalTextSpan) -> bool:
    """Return whether two spans share terminal styling attributes."""

    return left.foreground == right.foreground and left.bold == right.bold


__all__ = [
    "TerminalStyledLine",
    "TerminalTextSpan",
    "parse_ansi_sgr_record",
]
