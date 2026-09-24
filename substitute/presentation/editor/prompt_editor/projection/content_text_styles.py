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

"""Prepare immutable font and color styles for projection text runs."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont, QPalette

from substitute.application.appearance import SemanticPalette
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)

from .text_style import projection_text_run_font


@dataclass(frozen=True, slots=True)
class PromptProjectionTextPaintStyle:
    """Contain the prepared Qt values used to draw one text run."""

    font: QFont
    color: QColor


class PromptProjectionBaseTextStyles:
    """Own lazily prepared base styles for one projection and theme."""

    def __init__(
        self,
        projection_document: PromptProjectionDocument,
        *,
        fallback_font: QFont,
        fallback_color: QColor,
        selected_color: QColor,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
    ) -> None:
        """Retain style inputs and defer work until a run is actually painted."""

        self._projection_document = projection_document
        self._styles_by_run_id: dict[str, PromptProjectionTextPaintStyle] = {}
        self._fallback_font = QFont(fallback_font)
        self._fallback_color = QColor(fallback_color)
        self._selected_color = QColor(selected_color)
        self._palette = QPalette(palette)
        self._semantic_palette = semantic_palette

    @property
    def fallback_font(self) -> QFont:
        """Return the prepared font used when a fragment has no run."""

        return self._fallback_font

    @property
    def fallback_color(self) -> QColor:
        """Return the prepared color used when a fragment has no run."""

        return self._fallback_color

    @property
    def selected_color(self) -> QColor:
        """Return the prepared selected-text foreground color."""

        return self._selected_color

    def style_for_run(self, run_id: str) -> PromptProjectionTextPaintStyle | None:
        """Return one cached base style, preparing it on first visible use."""

        prepared = self._styles_by_run_id.get(run_id)
        if prepared is not None:
            return prepared
        run = self._projection_document.run_by_id(run_id)
        if run is None:
            return None
        prepared = text_style_for_run(
            run,
            base_font=self._fallback_font,
            palette=self._palette,
            semantic_palette=self._semantic_palette,
        )
        self._styles_by_run_id[run_id] = prepared
        return prepared


def prepare_base_text_styles(
    projection_document: PromptProjectionDocument,
    *,
    base_font: QFont,
    palette: QPalette,
    semantic_palette: SemanticPalette | None,
) -> PromptProjectionBaseTextStyles:
    """Prepare immutable style inputs without walking the full document."""

    return PromptProjectionBaseTextStyles(
        projection_document,
        fallback_font=base_font,
        fallback_color=palette.color(QPalette.ColorRole.Text),
        selected_color=palette.color(QPalette.ColorRole.HighlightedText),
        palette=palette,
        semantic_palette=semantic_palette,
    )


def text_style_for_run(
    run: PromptProjectionRun,
    *,
    base_font: QFont,
    palette: QPalette,
    semantic_palette: SemanticPalette | None,
) -> PromptProjectionTextPaintStyle:
    """Prepare font and foreground values for one effective run."""

    if run.ghosted:
        color = QColor(palette.color(QPalette.ColorRole.PlaceholderText))
    elif run.text_style_variant == "scene_error" and semantic_palette is not None:
        error = semantic_palette.error_foreground
        color = QColor(error.red, error.green, error.blue)
    else:
        color = QColor(palette.color(QPalette.ColorRole.Text))
    return PromptProjectionTextPaintStyle(
        font=projection_text_run_font(run, base_font),
        color=color,
    )


__all__ = [
    "PromptProjectionBaseTextStyles",
    "PromptProjectionTextPaintStyle",
    "prepare_base_text_styles",
    "text_style_for_run",
]
