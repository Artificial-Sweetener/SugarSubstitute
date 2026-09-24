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

"""Prepare pointer-owned token-weight preview feedback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QFont, QFontMetricsF

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)

from .token_weight_identity import tokens_share_content_range


class PromptTokenWeightPreviewTokenResolver(Protocol):
    """Resolve current projection tokens after a weight mutation."""

    def current_token_for(
        self,
        token: PromptProjectionToken,
    ) -> PromptProjectionToken | None:
        """Return the current token sharing the supplied token's identity."""


@dataclass(frozen=True, slots=True)
class PromptTokenWeightPreview:
    """Describe one host-local pointer preview ready for transient display."""

    text: str
    rect: QRectF


class PromptTokenWeightPreviewController:
    """Own preview text resolution, layout, clamping, and token remapping."""

    DURATION_MS = 240
    _CURSOR_OFFSET = 4.0
    _HOST_MARGIN = 6.0
    _HORIZONTAL_PADDING = 3.5
    _VERTICAL_PADDING = 1.0

    def prepare(
        self,
        token: PromptProjectionToken | None,
        *,
        pointer_host_position: QPointF | None,
        host_rect: QRectF,
        base_font: QFont,
    ) -> PromptTokenWeightPreview | None:
        """Return clamped host-local preview state for one updated token."""

        if token is None or token.value_text is None or pointer_host_position is None:
            return None
        text = (
            token.wildcard_display_tag
            if token.kind is PromptProjectionTokenKind.WILDCARD
            else token.value_text
        )
        if text is None or host_rect.isNull():
            return None
        metrics = QFontMetricsF(token_weight_preview_font(base_font))
        rect = QRectF(
            0.0,
            0.0,
            metrics.horizontalAdvance(text) + self._HORIZONTAL_PADDING * 2.0,
            metrics.height() + self._VERTICAL_PADDING * 2.0,
        )
        rect.moveLeft(pointer_host_position.x() - rect.width() / 2.0)
        rect.moveTop(pointer_host_position.y() - self._CURSOR_OFFSET - rect.height())
        rect.moveLeft(
            max(
                host_rect.left() + self._HOST_MARGIN,
                min(
                    rect.left(),
                    host_rect.right() - rect.width() - self._HOST_MARGIN,
                ),
            )
        )
        rect.moveTop(
            max(
                host_rect.top() + self._HOST_MARGIN,
                min(
                    rect.top(),
                    host_rect.bottom() - rect.height() - self._HOST_MARGIN,
                ),
            )
        )
        return PromptTokenWeightPreview(text=text, rect=rect)

    def resolve_post_action_token(
        self,
        source_token: PromptProjectionToken,
        *,
        visible_token: PromptProjectionToken | None,
        geometry_snapshot: PromptTokenWeightPreviewTokenResolver,
    ) -> PromptProjectionToken | None:
        """Resolve the current token that owns feedback after a prompt mutation."""

        resolved_token = geometry_snapshot.current_token_for(source_token)
        if resolved_token is not None:
            return resolved_token
        if visible_token is not None and tokens_share_content_range(
            visible_token, source_token
        ):
            return visible_token
        if visible_token is not None and visible_token.kind is source_token.kind:
            return visible_token
        return None


def token_weight_preview_font(base_font: QFont) -> QFont:
    """Return the font shared by preview measurement and painting."""

    font = QFont(base_font)
    if font.pointSizeF() > 0:
        font.setPointSizeF(max(8.0, font.pointSizeF() - 1.0))
    else:
        font.setPixelSize(max(12, font.pixelSize() - 1))
    return font


__all__ = [
    "PromptTokenWeightPreview",
    "PromptTokenWeightPreviewController",
    "token_weight_preview_font",
]
