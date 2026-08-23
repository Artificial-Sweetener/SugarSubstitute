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

"""Read valid transient projection state from a mounted prompt editor."""

from __future__ import annotations

from collections.abc import Sequence
import math

from PySide6.QtCore import QRectF


def valid_insertion_overlay(
    *,
    transient_overlays: object | None,
    freshness_is_stale_safe: bool,
    source_identity: object,
) -> object | None:
    """Return insertion overlay validity from the production overlay owner."""

    lookup = getattr(transient_overlays, "valid_insertion_overlay", None)
    if not callable(lookup) or source_identity is None:
        return None
    result: object = lookup(
        freshness_is_stale_safe=freshness_is_stale_safe,
        source_identity=source_identity,
    )
    return result


def valid_deletion_overlay(
    *,
    transient_overlays: object | None,
    freshness_is_stale_safe: bool,
    source_identity: object,
) -> object | None:
    """Return deletion overlay validity from the production overlay owner."""

    lookup = getattr(transient_overlays, "valid_deletion_overlay", None)
    if not callable(lookup) or source_identity is None:
        return None
    result: object = lookup(
        freshness_is_stale_safe=freshness_is_stale_safe,
        source_identity=source_identity,
    )
    return result


def valid_caret_geometry(
    *,
    transient_overlays: object | None,
    freshness_is_stale_safe: bool,
    source_identity: object,
    cursor_position: object,
    anchor_position: object,
) -> object | None:
    """Return caret-geometry validity from the production overlay owner."""

    lookup = getattr(transient_overlays, "valid_caret_geometry", None)
    if (
        not callable(lookup)
        or source_identity is None
        or not isinstance(cursor_position, int)
        or not isinstance(anchor_position, int)
    ):
        return None
    result: object = lookup(
        freshness_is_stale_safe=freshness_is_stale_safe,
        source_identity=source_identity,
        cursor_position=cursor_position,
        anchor_position=anchor_position,
    )
    return result


def _scrollbar_minimum(scrollbar: object | None) -> int:
    """Return one scrollbar minimum or zero for missing test doubles."""

    minimum = getattr(scrollbar, "minimum", None)
    return int(minimum()) if callable(minimum) else 0


def _scrollbar_maximum(scrollbar: object | None) -> int:
    """Return one scrollbar maximum or zero for missing test doubles."""

    maximum = getattr(scrollbar, "maximum", None)
    return int(maximum()) if callable(maximum) else 0


def _scrollbar_page_step(scrollbar: object | None) -> int:
    """Return one scrollbar page step or zero for missing test doubles."""

    page_step = getattr(scrollbar, "pageStep", None)
    return int(page_step()) if callable(page_step) else 0


def _surface_caret_rect(surface: object | None) -> QRectF | None:
    """Return the current surface-owned caret rect without painting."""

    current_caret_rect = getattr(surface, "_current_caret_rect", None)
    if not callable(current_caret_rect):
        return None
    rect = current_caret_rect()
    return QRectF(rect) if isinstance(rect, QRectF) else None


def _surface_scroll_offset(surface: object | None) -> float:
    """Return the projection surface scroll offset used by paint geometry owners."""

    scroll_offset = getattr(surface, "_scroll_offset", None)
    if not callable(scroll_offset):
        return 0.0
    result = scroll_offset()
    return float(result) if isinstance(result, int | float) else 0.0


def _transient_insertion_overlay_viewport_rect(
    *,
    transient_overlays: object | None,
    overlay: object | None,
    metrics: object | None,
    scroll_offset: float,
) -> QRectF | None:
    """Return the owner-computed viewport rect for a valid insertion overlay."""

    if overlay is None or metrics is None:
        return None
    viewport_rect = getattr(transient_overlays, "insertion_overlay_viewport_rect", None)
    if not callable(viewport_rect):
        return None
    result = viewport_rect(
        overlay,
        metrics=metrics,
        scroll_offset=scroll_offset,
    )
    return QRectF(result) if isinstance(result, QRectF) else None


def _transient_insertion_overlay_repaint_rect(
    *,
    transient_overlays: object | None,
    overlay: object | None,
    metrics: object | None,
    scroll_offset: float,
) -> QRectF | None:
    """Return the owner-computed repaint rect for a valid insertion overlay."""

    if overlay is None or metrics is None:
        return None
    repaint_rect = getattr(transient_overlays, "insertion_overlay_repaint_rect", None)
    if not callable(repaint_rect):
        return None
    result = repaint_rect(
        previous_overlay=None,
        next_overlay=overlay,
        metrics=metrics,
        scroll_offset=scroll_offset,
    )
    return QRectF(result) if isinstance(result, QRectF) else None


def _transient_deletion_overlay_viewport_rects(
    *,
    transient_overlays: object | None,
    overlay: object | None,
    scroll_offset: float,
) -> tuple[QRectF, ...]:
    """Return owner-computed viewport rects for a valid deletion overlay."""

    if overlay is None:
        return ()
    viewport_rects = getattr(
        transient_overlays, "deletion_overlay_viewport_rects", None
    )
    if not callable(viewport_rects):
        return ()
    return _qrectf_sequence(viewport_rects(overlay, scroll_offset=scroll_offset))


def _transient_deletion_overlay_erase_rects(
    *,
    transient_overlays: object | None,
    overlay: object | None,
    scroll_offset: float,
) -> tuple[QRectF, ...]:
    """Return owner-computed erase rects for a valid deletion overlay."""

    if overlay is None:
        return ()
    erase_rects = getattr(transient_overlays, "deletion_overlay_erase_rects", None)
    if not callable(erase_rects):
        return ()
    return _qrectf_sequence(erase_rects(overlay, scroll_offset=scroll_offset))


def _transient_deletion_overlay_repaint_rect(
    *,
    transient_overlays: object | None,
    overlay: object | None,
    scroll_offset: float,
) -> QRectF | None:
    """Return the owner-computed repaint rect for a valid deletion overlay."""

    if overlay is None:
        return None
    repaint_rect = getattr(transient_overlays, "deletion_overlay_repaint_rect", None)
    if not callable(repaint_rect):
        return None
    result = repaint_rect(
        previous_overlay=None,
        next_overlay=overlay,
        scroll_offset=scroll_offset,
    )
    return QRectF(result) if isinstance(result, QRectF) else None


def _qrectf_sequence(value: object) -> tuple[QRectF, ...]:
    """Return a tuple of QRectF values from an owner-returned sequence."""

    if not isinstance(value, Sequence):
        return ()
    return tuple(QRectF(rect) for rect in value if isinstance(rect, QRectF))


def _rectf_tuple(rect: QRectF | None) -> tuple[float, float, float, float] | None:
    """Serialize one QRectF for headless diagnostics."""

    if rect is None:
        return None
    return rect.x(), rect.y(), rect.width(), rect.height()


def _rectfs_tuple(
    rects: Sequence[QRectF],
) -> tuple[
    tuple[float, float, float, float],
    ...,
]:
    """Serialize QRectF values for headless diagnostics."""

    return tuple(
        rect_tuple for rect in rects if (rect_tuple := _rectf_tuple(rect)) is not None
    )


def _rectf_is_finite(rect: QRectF | None) -> bool:
    """Return whether one QRectF contains only finite coordinates."""

    if rect is None:
        return False
    return all(
        math.isfinite(value)
        for value in (rect.x(), rect.y(), rect.width(), rect.height())
    )
