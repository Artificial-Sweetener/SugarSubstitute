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

"""Resolve text styling shared by prompt projection layout and painting."""

from __future__ import annotations

from PySide6.QtGui import QFont

from .model import PromptProjectionRun

_BOLD_TEXT_STYLE_VARIANTS = frozenset({"scene_title", "scene_error"})


def projection_text_run_font(
    run: PromptProjectionRun,
    base_font: QFont,
) -> QFont:
    """Return the rendered font for one projection text run."""

    font = QFont(base_font)
    if run.text_style_variant in _BOLD_TEXT_STYLE_VARIANTS:
        font.setWeight(QFont.Weight.Bold)
    return font


__all__ = ["projection_text_run_font"]
