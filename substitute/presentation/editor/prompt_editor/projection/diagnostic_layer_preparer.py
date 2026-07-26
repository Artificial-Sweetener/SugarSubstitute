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

"""Prepare viewport-bounded diagnostic underline render commands."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.diagnostics.models import PromptDiagnostic
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
)
from substitute.presentation.editor.prompt_editor.geometry.aggregate import (
    PromptProjectionGeometry,
)

from .diagnostic_fragment_cache import (
    PromptDiagnosticFragmentCache,
    diagnostic_fragment_key,
)
from .diagnostic_render_layer import (
    PromptDiagnosticRenderLayer,
    PromptDiagnosticUnderline,
)


class PromptDiagnosticLayerPreparer:
    """Own visible diagnostic selection and fragment-cache preparation."""

    def __init__(self) -> None:
        """Create a preparer with bounded revision-keyed fragment storage."""

        self._fragments = PromptDiagnosticFragmentCache()

    def prepare_visible_cached(
        self,
        *,
        diagnostics: Sequence[PromptDiagnostic],
        selection: PromptProjectionSelection,
        preview_geometry: PromptProjectionGeometry | None,
        viewport_rect: QRectF,
        scroll_offset: float,
        layout_identity: PromptLayoutIdentity,
        color_rgba: int,
    ) -> tuple[PromptDiagnosticRenderLayer, tuple[PromptDiagnostic, ...]]:
        """Prepare commands for visible diagnostics and report cache misses."""

        underlines: list[PromptDiagnosticUnderline] = []
        missing: list[PromptDiagnostic] = []
        for diagnostic in diagnostics:
            if not selection.is_empty and _ranges_overlap(
                selection.start,
                selection.end,
                diagnostic.source_start,
                diagnostic.source_end,
            ):
                continue
            if preview_geometry is not None:
                prepared_fragments = preview_geometry.selection.source_range_fragments(
                    start=diagnostic.source_start,
                    end=diagnostic.source_end,
                    viewport_rect=viewport_rect,
                    scroll_offset=scroll_offset,
                )
            else:
                key = diagnostic_fragment_key(
                    diagnostic=diagnostic,
                    layout_identity=layout_identity,
                    viewport_rect=viewport_rect,
                    scroll_offset=scroll_offset,
                )
                cached_fragments = self._fragments.get(key)
                if cached_fragments is None:
                    missing.append(diagnostic)
                    continue
                prepared_fragments = cached_fragments
            underlines.extend(_prepared_underlines(prepared_fragments))
        return (
            PromptDiagnosticRenderLayer(
                color_rgba=color_rgba,
                underlines=tuple(underlines),
            ),
            tuple(missing),
        )

    def visible_diagnostics(
        self,
        diagnostics: Sequence[PromptDiagnostic],
        *,
        geometry: PromptProjectionGeometry,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[PromptDiagnostic, ...]:
        """Return diagnostics whose source ranges can intersect the viewport."""

        source_bounds = geometry.viewport.visible_source_bounds(
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        if source_bounds is None:
            return ()
        visible_start, visible_end = source_bounds
        return tuple(
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.source_start < visible_end
            and diagnostic.source_end > visible_start
        )

    def fragments(
        self,
        diagnostic: PromptDiagnostic,
        *,
        geometry: PromptProjectionGeometry,
        viewport_rect: QRectF,
        scroll_offset: float,
        layout_identity: PromptLayoutIdentity,
    ) -> tuple[QRectF, ...]:
        """Return retained or newly prepared geometry for one diagnostic."""

        key = diagnostic_fragment_key(
            diagnostic=diagnostic,
            layout_identity=layout_identity,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        return self._fragments.get_or_build(
            key,
            lambda: tuple(
                geometry.selection.source_range_fragments(
                    start=diagnostic.source_start,
                    end=diagnostic.source_end,
                    viewport_rect=viewport_rect,
                    scroll_offset=scroll_offset,
                )
            ),
        )

    def contains(
        self,
        diagnostic: PromptDiagnostic,
        *,
        layout_identity: PromptLayoutIdentity,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> bool:
        """Return whether exact prepared fragments already exist."""

        return self._fragments.contains(
            diagnostic_fragment_key(
                diagnostic=diagnostic,
                layout_identity=layout_identity,
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
            )
        )

    def clear(self) -> None:
        """Discard fragment geometry after an incompatible owner revision."""

        self._fragments.clear()

    def preserve_for_incremental_edit(
        self,
        *,
        diagnostics: Sequence[PromptDiagnostic],
        start: int,
        end: int,
        replacement_text: str,
        previous_layout_identity: PromptLayoutIdentity,
        next_layout_identity: PromptLayoutIdentity,
        fragment_y_delta: float = 0.0,
    ) -> None:
        """Remap unaffected prepared fragments across one incremental edit."""

        self._fragments.preserve_for_incremental_edit(
            diagnostics=diagnostics,
            start=start,
            end=end,
            replacement_text=replacement_text,
            previous_layout_identity=previous_layout_identity,
            next_layout_identity=next_layout_identity,
            fragment_y_delta=fragment_y_delta,
        )


def _prepared_underlines(
    fragments: Sequence[QRectF],
) -> tuple[PromptDiagnosticUnderline, ...]:
    """Copy mutable Qt rectangles into immutable scalar draw commands."""

    return tuple(
        PromptDiagnosticUnderline(
            left=fragment.left(),
            bottom=fragment.bottom(),
            width=fragment.width(),
            height=fragment.height(),
        )
        for fragment in fragments
    )


def _ranges_overlap(
    first_start: int,
    first_end: int,
    second_start: int,
    second_end: int,
) -> bool:
    """Return whether two half-open source ranges overlap."""

    return first_start < second_end and second_start < first_end


__all__ = ["PromptDiagnosticLayerPreparer"]
