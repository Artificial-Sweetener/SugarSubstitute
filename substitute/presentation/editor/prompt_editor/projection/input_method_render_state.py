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

"""Define immutable shaped input-method state published before paint."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QTextCharFormat, QTextLayout

from substitute.presentation.editor.prompt_editor.core.editing.ime import (
    PromptImePreedit,
)


@dataclass(frozen=True, slots=True)
class PromptPreeditFormat:
    """Describe one detached UTF-16 preedit format range."""

    start: int
    length: int
    text_format: QTextCharFormat


@dataclass(frozen=True, slots=True)
class PromptInputMethodLayerKey:
    """Identify one exact preedit, geometry, font, palette, and format state."""

    preedit: PromptImePreedit
    formats: tuple[PromptPreeditFormat, ...]
    origin: tuple[int, int]
    font_key: str
    palette_key: int
    cursor_rgba: int


@dataclass(frozen=True, slots=True)
class PromptInputMethodRenderLayer:
    """Contain one shaped preedit layout and its prepared cursor geometry."""

    key: PromptInputMethodLayerKey | None
    layout: QTextLayout | None
    origin: tuple[float, float]
    cursor_line: tuple[float, float, float, float] | None
    cursor_rgba: int
    candidate_rect: tuple[float, float, float, float] | None


EMPTY_INPUT_METHOD_RENDER_LAYER = PromptInputMethodRenderLayer(
    key=None,
    layout=None,
    origin=(0.0, 0.0),
    cursor_line=None,
    cursor_rgba=0,
    candidate_rect=None,
)


__all__ = [
    "EMPTY_INPUT_METHOD_RENDER_LAYER",
    "PromptInputMethodLayerKey",
    "PromptInputMethodRenderLayer",
    "PromptPreeditFormat",
]
