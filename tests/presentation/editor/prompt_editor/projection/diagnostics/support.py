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

"""Diagnostic projection helpers for real-surface contracts."""

from __future__ import annotations


from typing import Any, cast

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage

from substitute.application.prompt_editor.diagnostics.models import PromptDiagnostic
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
    PromptLayoutRevision,
    PromptProjectionIdentity,
    PromptProjectionRevision,
    PromptSemanticIdentity,
    PromptSemanticRevision,
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.geometry.selection import (
    PromptSelectionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def wait_for_diagnostic_layer(
    surface: PromptProjectionSurface,
    *,
    has_underlines: bool,
) -> None:
    """Wait for diagnostic publication and bounded fragment warming to finish."""

    owner = cast(Any, surface)._diagnostic_layer_owner

    def layer_is_ready() -> bool:
        """Return whether publication and its warming lifecycle are complete."""

        return (
            bool(owner.layer.underlines) is has_underlines
            and owner._warm_state is None
            and not owner._warm_timer.isActive()
        )

    def layer_state() -> object:
        """Describe current publication and warming state for timeout evidence."""

        warm_state = owner._warm_state
        return {
            "underline_count": len(owner.layer.underlines),
            "expected_underlines": has_underlines,
            "warm_timer_active": owner._warm_timer.isActive(),
            "warm_index": owner._warm_index,
            "missing_count": (
                0 if warm_state is None else len(warm_state.missing_diagnostics)
            ),
            "revision": owner.layer.revision,
        }

    wait_for_qt_condition(
        layer_is_ready,
        description="prompt diagnostic layer publication",
        state=layer_state,
    )


def _observe_source_range_fragment_lookups(
    monkeypatch: pytest.MonkeyPatch,
) -> list[int]:
    """Count calls at the authoritative selection-geometry owner."""

    lookup_count = [0]
    original = PromptSelectionGeometry.source_range_fragments

    def observed_source_range_fragments(
        selection_geometry: PromptSelectionGeometry,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Record one lookup while preserving selection geometry behavior."""

        lookup_count[0] += 1
        return original(
            selection_geometry,
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    monkeypatch.setattr(
        PromptSelectionGeometry,
        "source_range_fragments",
        observed_source_range_fragments,
    )
    return lookup_count


def _diagnostic_fragments(
    surface: object,
    diagnostic: PromptDiagnostic,
    *,
    viewport_rect: QRectF,
    scroll_offset: float,
) -> tuple[QRectF, ...]:
    """Query retained fragments through the authoritative diagnostic owner."""

    prompt_surface = cast(Any, surface)
    layout_identity = prompt_surface._frame_state.current_layout_identity(
        prompt_surface._layout.frame.output
    )
    assert layout_identity is not None
    return cast(
        tuple[QRectF, ...],
        prompt_surface._diagnostic_layer_owner.fragments(
            diagnostic,
            geometry=prompt_surface._layout.frame.geometry,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_identity=layout_identity,
        ),
    )


def _changed_pixel_distance(before: QImage, after: QImage, x: int, y: int) -> int:
    """Return the channel distance between two rendered pixels."""

    first = before.pixelColor(x, y)
    second = after.pixelColor(x, y)
    return (
        abs(first.red() - second.red())
        + abs(first.green() - second.green())
        + abs(first.blue() - second.blue())
        + abs(first.alpha() - second.alpha())
    )


def _diagnostic_column_centers(
    before: QImage,
    after: QImage,
    fragment: QRectF,
) -> tuple[float, ...]:
    """Return per-column centers of pixels introduced by a spelling diagnostic."""

    left = max(0, int(fragment.left()) - 1)
    right = min(after.width() - 1, int(fragment.right()) + 1)
    top = max(0, int(fragment.bottom()) - 8)
    bottom = min(after.height() - 1, int(fragment.bottom()) + 2)
    centers: list[float] = []
    for x in range(left, right + 1):
        changed_rows = [
            y
            for y in range(top, bottom + 1)
            if _changed_pixel_distance(before, after, x, y) > 24
        ]
        if changed_rows:
            centers.append(sum(changed_rows) / len(changed_rows))
    return tuple(centers)


def _next_layout_identity(
    previous: PromptLayoutIdentity,
    *,
    next_source_length: int,
) -> PromptLayoutIdentity:
    """Return one exact successor lineage for cache-remap tests."""

    previous_semantic = previous.projection.semantic
    source = PromptSourceIdentity(
        previous_semantic.source.source_revision + 1,
        next_source_length,
    )
    semantic = PromptSemanticIdentity(
        source,
        PromptSemanticRevision(int(previous_semantic.semantic_revision) + 1),
    )
    projection = PromptProjectionIdentity(
        semantic,
        PromptProjectionRevision(int(previous.projection.projection_revision) + 1),
    )
    return PromptLayoutIdentity(
        projection,
        PromptLayoutRevision(int(previous.layout_revision) + 1),
    )
