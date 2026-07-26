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

"""Build complete prompt layout configuration and matching font metrics."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtGui import QFont

from ..projection.metrics import PromptProjectionMetricsFactory
from ..projection.tokens import PromptProjectionInlineObjectRendererRegistry
from .contracts import PromptLayoutConfiguration


@dataclass(slots=True)
class PromptLayoutConfigurationFactory:
    """Own normalized geometry inputs and their matching metrics."""

    inline_object_renderers: PromptProjectionInlineObjectRendererRegistry
    document_margin: float = 4.0
    _metrics_factory: PromptProjectionMetricsFactory = field(init=False)

    def __post_init__(self) -> None:
        """Create the renderer-independent metrics factory once."""

        self._metrics_factory = PromptProjectionMetricsFactory()

    def create(
        self,
        *,
        base_font: QFont,
        text_width: float,
        content_left_inset: float = 0.0,
    ) -> PromptLayoutConfiguration:
        """Return one normalized complete configuration."""

        normalized_width = self.normalize_text_width(text_width)
        normalized_inset = self.normalize_content_left_inset(content_left_inset)
        metrics = self._metrics_factory.create(
            base_font=base_font,
            document_margin=self.document_margin,
            wrap_width=normalized_width,
            content_left_inset=normalized_inset,
        )
        return PromptLayoutConfiguration(
            base_font=base_font,
            document_margin=self.document_margin,
            text_width=normalized_width,
            content_left_inset=normalized_inset,
            metrics=metrics,
            inline_object_renderers=self.inline_object_renderers,
        )

    def update(
        self,
        current: PromptLayoutConfiguration,
        *,
        base_font: QFont | None = None,
        text_width: float | None = None,
        content_left_inset: float | None = None,
    ) -> PromptLayoutConfiguration:
        """Return one complete configuration derived from current values."""

        return self.create(
            base_font=current.base_font if base_font is None else base_font,
            text_width=current.text_width if text_width is None else text_width,
            content_left_inset=(
                current.content_left_inset
                if content_left_inset is None
                else content_left_inset
            ),
        )

    @staticmethod
    def normalize_text_width(width: float) -> float:
        """Return a non-pathological projection wrapping width."""

        return max(1.0, width)

    @staticmethod
    def normalize_content_left_inset(inset: float) -> float:
        """Return a non-negative content inset."""

        return max(0.0, inset)


__all__ = ["PromptLayoutConfigurationFactory"]
