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

"""Serialize prompt-domain documents and deterministic segment mutations."""

from __future__ import annotations

from collections.abc import Sequence

from .models import PromptDocument


def serialize_prompt_document(document: PromptDocument) -> str:
    """Return the exact source text represented by the parsed prompt document."""

    return document.source_text


def normalize_reorder_separator_text(separator_text: str) -> str:
    """Preserve one separator slot for reorder preview and commit behavior."""

    return separator_text


def serialize_segments(
    segment_texts: Sequence[str],
    *,
    has_trailing_comma: bool,
) -> str:
    """Serialize top-level prompt segments using canonical separators."""

    serialized = ", ".join(segment_texts)
    if has_trailing_comma:
        if serialized:
            return f"{serialized}, "
        return ", "
    return serialized


__all__ = [
    "normalize_reorder_separator_text",
    "serialize_prompt_document",
    "serialize_segments",
]
