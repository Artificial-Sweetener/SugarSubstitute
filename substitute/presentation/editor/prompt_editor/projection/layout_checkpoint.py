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
from substitute.application.prompt_editor import PromptDocumentView

from .model import PromptProjectionDocument
from .snapshot import PromptProjectionLayoutSnapshot


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


__all__ = [
    "PromptProjectionLayoutCheckpoint",
    "PromptProjectionLayoutCheckpointKey",
]
