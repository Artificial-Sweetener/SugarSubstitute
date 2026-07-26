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

"""Prepare viewport-bounded selection commands for projection content."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPalette

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.geometry.aggregate import (
    PromptProjectionGeometry,
)
from substitute.presentation.editor.prompt_editor.geometry.visible_lines import (
    visible_projection_lines,
)
from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLayoutSnapshot,
    PromptProjectionTextFragment,
)

from .content_inline_bindings import PromptProjectionBaseInlineBindings


@dataclass(frozen=True, slots=True)
class PromptProjectionSelectionRect:
    """Describe one immutable document-local selection fill."""

    left: float
    top: float
    width: float
    height: float


class PromptProjectionSelectionLayer:
    """Contain prepared selection backgrounds and fragment foreground state."""

    def __init__(
        self,
        *,
        selection: PromptProjectionSelection | None,
        background_rgba: int,
        backgrounds: tuple[PromptProjectionSelectionRect, ...],
        text_spans: Mapping[int, tuple[int, int]],
        selected_inline_fragment_ids: frozenset[int],
    ) -> None:
        """Retain immutable selection commands behind exact fragment identities."""

        self._selection = selection
        self._background_rgba = background_rgba
        self._backgrounds = backgrounds
        self._text_spans = MappingProxyType(dict(text_spans))
        self._selected_inline_fragment_ids = selected_inline_fragment_ids

    @property
    def is_empty(self) -> bool:
        """Return whether this layer represents no selected source range."""

        return self._selection is None or self._selection.is_empty

    @property
    def background_rgba(self) -> int:
        """Return the prepared selection background color."""

        return self._background_rgba

    @property
    def backgrounds(self) -> tuple[PromptProjectionSelectionRect, ...]:
        """Return prepared document-local selection fills."""

        return self._backgrounds

    def text_span(
        self,
        fragment: PromptProjectionTextFragment,
    ) -> tuple[int, int] | None:
        """Return the selected character bounds for one text fragment."""

        return self._text_spans.get(id(fragment))

    def inline_fragment_is_selected(
        self,
        fragment: PromptProjectionInlineObjectFragment,
    ) -> bool:
        """Return whether one inline fragment uses selected foreground colors."""

        return id(fragment) in self._selected_inline_fragment_ids


EMPTY_PROJECTION_SELECTION_LAYER = PromptProjectionSelectionLayer(
    selection=None,
    background_rgba=0,
    backgrounds=(),
    text_spans={},
    selected_inline_fragment_ids=frozenset(),
)


def prepare_projection_selection_layer(
    selection: PromptProjectionSelection,
    *,
    geometry: PromptProjectionGeometry,
    layout_snapshot: PromptProjectionLayoutSnapshot,
    inline_bindings: PromptProjectionBaseInlineBindings,
    viewport_rect: QRectF,
    scroll_offset: float,
    palette: QPalette,
) -> PromptProjectionSelectionLayer:
    """Prepare only selection commands intersecting the current viewport."""

    if selection.is_empty:
        return EMPTY_PROJECTION_SELECTION_LAYER
    document_viewport = viewport_rect.translated(0.0, scroll_offset)
    backgrounds = tuple(
        PromptProjectionSelectionRect(
            left=rect.left(),
            top=rect.top(),
            width=rect.width(),
            height=rect.height(),
        )
        for rect in geometry.selection.selection_rects(selection)
        if rect.intersects(document_viewport)
    )
    text_spans: dict[int, tuple[int, int]] = {}
    selected_inline_ids: set[int] = set()
    for line in visible_projection_lines(
        layout_snapshot.lines,
        document_top=document_viewport.top(),
        document_bottom=document_viewport.bottom(),
    ):
        for fragment in line.fragments:
            if isinstance(fragment, PromptProjectionTextFragment):
                bounds = geometry.selection.text_fragment_selection_bounds(
                    fragment,
                    selection,
                )
                if bounds is not None:
                    text_spans[id(fragment)] = bounds
                continue
            binding = inline_bindings.binding(fragment)
            if binding is not None and _inline_fragment_selected(
                binding.token.source_start,
                binding.token.source_end,
                fragment,
                selection,
            ):
                selected_inline_ids.add(id(fragment))
    return PromptProjectionSelectionLayer(
        selection=selection,
        background_rgba=int(palette.color(QPalette.ColorRole.Highlight).rgba()),
        backgrounds=backgrounds,
        text_spans=text_spans,
        selected_inline_fragment_ids=frozenset(selected_inline_ids),
    )


def _inline_fragment_selected(
    token_start: int,
    token_end: int,
    fragment: PromptProjectionInlineObjectFragment,
    selection: PromptProjectionSelection,
) -> bool:
    """Return whether selection covers one token or fragment source span."""

    if selection.start <= token_start and token_end <= selection.end:
        return True
    if len(fragment.source_positions) < 2:
        return False
    source_start = fragment.source_positions[0]
    source_end = fragment.source_positions[-1]
    return selection.start < source_end and source_start < selection.end


__all__ = [
    "EMPTY_PROJECTION_SELECTION_LAYER",
    "PromptProjectionSelectionLayer",
    "PromptProjectionSelectionRect",
    "prepare_projection_selection_layer",
]
