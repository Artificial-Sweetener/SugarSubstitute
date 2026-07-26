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

"""Measure projection tokens through their prepared renderer inputs."""

from __future__ import annotations

from PySide6.QtCore import QSizeF
from PySide6.QtGui import QFont, QFontMetricsF

from ..core.projection.document import PromptProjectionDocument
from ..core.projection.runs import PromptProjectionRunKind
from ..core.projection.tokens import PromptProjectionToken
from ..projection.metrics import PromptProjectionMetrics
from ..projection.text_style import projection_text_run_font
from ..projection.tokens import PromptProjectionInlineObjectRendererRegistry


class PromptProjectionTokenMeasurer:
    """Own renderer-backed measurement of one prepared projection token."""

    def measure(
        self,
        token: PromptProjectionToken,
        *,
        projection_document: PromptProjectionDocument,
        inline_object_renderers: PromptProjectionInlineObjectRendererRegistry,
        base_font: QFont,
        metrics: PromptProjectionMetrics,
    ) -> QSizeF:
        """Return the visible size of every run owned by one token."""

        runs = projection_document.runs_for_token(token.token_id)
        if not runs:
            return QSizeF(0.0, 0.0)
        width = 0.0
        height = 0.0
        for run in runs:
            if run.kind is PromptProjectionRunKind.TEXT:
                run_metrics = QFontMetricsF(projection_text_run_font(run, base_font))
                width += run_metrics.horizontalAdvance(run.display_text)
                height = max(height, metrics.text_line_height)
                continue
            renderer = inline_object_renderers.renderer_for(run.renderer_key)
            if renderer is None:
                continue
            size = renderer.measure_inline_object(
                run,
                token,
                base_font=base_font,
            )
            width += size.width()
            height = max(height, size.height())
        return QSizeF(width, height)


__all__ = ["PromptProjectionTokenMeasurer"]
