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

"""Define immutable transient edit commands and their revision identity."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QFont, QRegion

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from .transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientInsertionOverlay,
)


@dataclass(frozen=True, slots=True)
class PromptTransientEditLayerKey:
    """Identify exact transient, viewport, metric, font, and palette inputs."""

    source_identity: PromptSourceIdentity
    insertion: PromptProjectionTransientInsertionOverlay | None
    deletion: PromptProjectionTransientDeletionOverlay | None
    metrics_identity: int
    viewport: tuple[int, int, int, int]
    scroll_offset: int
    font_key: str
    palette_key: int


@dataclass(frozen=True, slots=True)
class PromptTransientInsertionCommand:
    """Describe one prepared viewport-local typed-text command."""

    text: str
    rect: tuple[float, float, float, float]
    baseline: float
    font: QFont
    text_rgba: int
    background_rgba: int


@dataclass(frozen=True, slots=True)
class PromptTransientDeletionCommand:
    """Describe one prepared viewport-local erase command."""

    rects: tuple[tuple[float, float, float, float], ...]
    background_rgba: int


@dataclass(frozen=True, slots=True)
class PromptTransientEditRenderLayer:
    """Contain complete prepared transient feedback for one render revision."""

    key: PromptTransientEditLayerKey | None
    insertion: PromptTransientInsertionCommand | None
    deletion: PromptTransientDeletionCommand | None
    content_visible_region: QRegion | None


EMPTY_TRANSIENT_EDIT_RENDER_LAYER = PromptTransientEditRenderLayer(
    key=None,
    insertion=None,
    deletion=None,
    content_visible_region=None,
)


__all__ = [
    "EMPTY_TRANSIENT_EDIT_RENDER_LAYER",
    "PromptTransientDeletionCommand",
    "PromptTransientEditLayerKey",
    "PromptTransientEditRenderLayer",
    "PromptTransientInsertionCommand",
]
