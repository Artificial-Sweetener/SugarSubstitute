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

"""Describe exact prompt layout checkpoints retained by editor history."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.appearance import SemanticPalette
from substitute.application.prompt_editor.document.views import PromptDocumentView

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from .contracts import PromptLayoutConfiguration, PromptLayoutOutput
from .models import PromptProjectionLayoutSnapshot


@dataclass(frozen=True, slots=True)
class PromptProjectionLayoutCheckpointKey:
    """Identify geometry inputs that make one layout checkpoint reusable."""

    font_key: str
    palette_key: int
    semantic_palette: SemanticPalette | None
    document_margin: float
    text_width: float
    content_left_inset: float


@dataclass(frozen=True, slots=True)
class PromptProjectionLayoutCheckpoint:
    """Retain exact canonical layout state through structurally shared snapshots."""

    key: PromptProjectionLayoutCheckpointKey
    projection_document: PromptProjectionDocument
    prompt_document_view: PromptDocumentView
    snapshot: PromptProjectionLayoutSnapshot


def capture_layout_checkpoint(
    output: PromptLayoutOutput,
    *,
    palette_key: int,
    semantic_palette: SemanticPalette | None,
) -> PromptProjectionLayoutCheckpoint | None:
    """Capture exact canonical state when source ownership is current."""

    prompt_document_view = output.prompt_document_view
    if (
        prompt_document_view is None
        or prompt_document_view.source_text != output.projection_document.source_text
    ):
        return None
    return PromptProjectionLayoutCheckpoint(
        key=layout_checkpoint_key(
            output.configuration,
            palette_key=palette_key,
            semantic_palette=semantic_palette,
        ),
        projection_document=output.projection_document,
        prompt_document_view=prompt_document_view,
        snapshot=output.snapshot,
    )


def restore_layout_checkpoint(
    checkpoint: PromptProjectionLayoutCheckpoint,
    *,
    configuration: PromptLayoutConfiguration,
    palette_key: int,
    semantic_palette: SemanticPalette | None,
) -> PromptLayoutOutput | None:
    """Return restored immutable output when every geometry input still matches."""

    if (
        checkpoint.key
        != layout_checkpoint_key(
            configuration,
            palette_key=palette_key,
            semantic_palette=semantic_palette,
        )
        or checkpoint.prompt_document_view.source_text
        != checkpoint.projection_document.source_text
    ):
        return None
    return PromptLayoutOutput(
        projection_document=checkpoint.projection_document,
        prompt_document_view=checkpoint.prompt_document_view,
        snapshot=checkpoint.snapshot,
        configuration=configuration,
    )


def layout_checkpoint_key(
    configuration: PromptLayoutConfiguration,
    *,
    palette_key: int,
    semantic_palette: SemanticPalette | None,
) -> PromptProjectionLayoutCheckpointKey:
    """Return exact geometry and visual identity for checkpoint restoration."""

    return PromptProjectionLayoutCheckpointKey(
        font_key=configuration.base_font.toString(),
        palette_key=palette_key,
        semantic_palette=semantic_palette,
        document_margin=configuration.document_margin,
        text_width=configuration.text_width,
        content_left_inset=configuration.content_left_inset,
    )


__all__ = [
    "PromptProjectionLayoutCheckpoint",
    "PromptProjectionLayoutCheckpointKey",
    "capture_layout_checkpoint",
    "layout_checkpoint_key",
    "restore_layout_checkpoint",
]
