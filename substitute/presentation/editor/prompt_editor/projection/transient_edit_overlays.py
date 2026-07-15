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

"""Own transient source-edit overlay state and geometry for projection catch-up."""

from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtCore import QRectF
from PySide6.QtGui import QRegion

from .layout_engine import PromptProjectionLayout
from .metrics import PromptProjectionMetrics
from .model import PromptProjectionCaretState, PromptProjectionDocument
from .selection_geometry import merge_same_row_rects


@dataclass(frozen=True, slots=True)
class PromptProjectionTransientCaretGeometry:
    """Bridge source-caret geometry while projected layout catches up."""

    source_revision: int
    cursor_position: int
    anchor_position: int
    document_rect: QRectF
    committed_source_revision: int


@dataclass(frozen=True, slots=True)
class PromptProjectionTransientInsertionOverlay:
    """Paint newly typed source text while projected layout catches up."""

    source_revision: int
    committed_source_revision: int
    source_start: int
    text: str
    document_rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptProjectionTransientDeletionOverlay:
    """Hide freshly deleted source text while projected layout catches up."""

    source_revision: int
    committed_source_revision: int
    source_start: int
    source_end: int
    document_rects: tuple[QRectF, ...]


class PromptProjectionTransientEditOverlayController:
    """Own transient edit overlay state, validation, and repaint geometry."""

    def __init__(self) -> None:
        """Create an empty transient overlay controller."""

        self._caret_geometry: PromptProjectionTransientCaretGeometry | None = None
        self._insertion_overlay: PromptProjectionTransientInsertionOverlay | None = None
        self._deletion_overlay: PromptProjectionTransientDeletionOverlay | None = None

    @property
    def caret_geometry(self) -> PromptProjectionTransientCaretGeometry | None:
        """Return the current transient caret geometry without validating it."""

        return self._caret_geometry

    @property
    def insertion_overlay(self) -> PromptProjectionTransientInsertionOverlay | None:
        """Return the current insertion overlay without validating it."""

        return self._insertion_overlay

    @property
    def deletion_overlay(self) -> PromptProjectionTransientDeletionOverlay | None:
        """Return the current deletion overlay without validating it."""

        return self._deletion_overlay

    def clear(self) -> None:
        """Discard all transient source-edit overlay state."""

        self._caret_geometry = None
        self._insertion_overlay = None
        self._deletion_overlay = None

    def set_overlays(
        self,
        *,
        caret_geometry: PromptProjectionTransientCaretGeometry | None,
        insertion_overlay: PromptProjectionTransientInsertionOverlay | None,
        deletion_overlay: PromptProjectionTransientDeletionOverlay | None,
    ) -> None:
        """Replace all transient overlay state for one deferred source edit."""

        self._caret_geometry = caret_geometry
        self._insertion_overlay = insertion_overlay
        self._deletion_overlay = deletion_overlay

    def valid_caret_geometry(
        self,
        *,
        freshness_is_stale_safe: bool,
        source_revision: int,
        cursor_position: int,
        anchor_position: int,
    ) -> PromptProjectionTransientCaretGeometry | None:
        """Return caret geometry when it still matches live source state."""

        geometry = self._caret_geometry
        if geometry is None:
            return None
        if not freshness_is_stale_safe:
            return None
        if geometry.source_revision != source_revision:
            return None
        if geometry.cursor_position != cursor_position:
            return None
        if geometry.anchor_position != anchor_position:
            return None
        return geometry

    def valid_insertion_overlay(
        self,
        *,
        freshness_is_stale_safe: bool,
        source_revision: int,
    ) -> PromptProjectionTransientInsertionOverlay | None:
        """Return a typed-text overlay when it still matches live source state."""

        overlay = self._insertion_overlay
        if overlay is None:
            return None
        if not freshness_is_stale_safe:
            return None
        if overlay.source_revision != source_revision:
            return None
        return overlay

    def valid_deletion_overlay(
        self,
        *,
        freshness_is_stale_safe: bool,
        source_revision: int,
    ) -> PromptProjectionTransientDeletionOverlay | None:
        """Return a deletion overlay when it still matches live source state."""

        overlay = self._deletion_overlay
        if overlay is None:
            return None
        if not freshness_is_stale_safe:
            return None
        if overlay.source_revision != source_revision:
            return None
        return overlay

    def valid_caret_document_rect(
        self,
        *,
        freshness_is_stale_safe: bool,
        source_revision: int,
        cursor_position: int,
        anchor_position: int,
    ) -> QRectF | None:
        """Return valid document-local caret geometry for transient projection."""

        geometry = self.valid_caret_geometry(
            freshness_is_stale_safe=freshness_is_stale_safe,
            source_revision=source_revision,
            cursor_position=cursor_position,
            anchor_position=anchor_position,
        )
        if geometry is None:
            return None
        return QRectF(geometry.document_rect)

    def can_defer_insertion_overlay(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        live_source_length: int,
        committed_source_length: int,
        caret_rect: QRectF,
        content_right: float,
        metrics: PromptProjectionMetrics,
        freshness_is_stale_safe: bool,
        source_revision: int,
    ) -> bool:
        """Return whether an insertion can be painted without changing layout."""

        if start != end:
            return False
        if len(replacement_text) != 1 or replacement_text in {"\n", "\r"}:
            return False
        if start not in {
            live_source_length,
            live_source_length - len(replacement_text),
        }:
            return False
        previous_overlay = self.valid_insertion_overlay(
            freshness_is_stale_safe=freshness_is_stale_safe,
            source_revision=source_revision,
        )
        if previous_overlay is None:
            if start != committed_source_length:
                return False
            pending_text = replacement_text
        else:
            overlay_end = previous_overlay.source_start + len(previous_overlay.text)
            if (
                previous_overlay.source_start != committed_source_length
                or start != overlay_end
            ):
                return False
            pending_text = f"{previous_overlay.text}{replacement_text}"

        overlay_width = metrics.text_advance(pending_text)
        return caret_rect.left() + overlay_width <= content_right + 0.01

    def single_character_edit_caret_geometry(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        cursor_position: int,
        anchor_position: int,
        source_revision: int,
        committed_source_revision: int,
        current_caret_document_rect: QRectF,
        metrics: PromptProjectionMetrics,
        projection_document: PromptProjectionDocument,
        layout: PromptProjectionLayout,
    ) -> PromptProjectionTransientCaretGeometry | None:
        """Return immediate caret geometry for one deferred single-character edit."""

        if replacement_text:
            if len(replacement_text) != 1 or replacement_text in {"\n", "\r"}:
                return None
            document_rect = QRectF(current_caret_document_rect).translated(
                metrics.text_advance(replacement_text),
                0.0,
            )
        elif end == start + 1:
            caret_state = projection_document.caret_map.state_for_source_position(start)
            document_rect = layout.cursor_rect(caret_state, scroll_offset=0.0)
        else:
            return None
        return PromptProjectionTransientCaretGeometry(
            source_revision=source_revision,
            cursor_position=cursor_position,
            anchor_position=anchor_position,
            committed_source_revision=committed_source_revision,
            document_rect=document_rect,
        )

    def single_character_insertion_overlay(
        self,
        *,
        start: int,
        replacement_text: str,
        source_revision: int,
        committed_source_revision: int,
        current_caret_document_rect: QRectF,
        freshness_is_stale_safe: bool,
        current_source_revision: int,
    ) -> PromptProjectionTransientInsertionOverlay | None:
        """Return text overlay for one deferred single-character insertion."""

        if len(replacement_text) != 1 or replacement_text in {"\n", "\r"}:
            return None
        previous_overlay = self.valid_insertion_overlay(
            freshness_is_stale_safe=freshness_is_stale_safe,
            source_revision=current_source_revision,
        )
        if (
            previous_overlay is not None
            and previous_overlay.committed_source_revision == committed_source_revision
            and previous_overlay.source_start + len(previous_overlay.text) == start
        ):
            return PromptProjectionTransientInsertionOverlay(
                source_revision=source_revision,
                committed_source_revision=committed_source_revision,
                source_start=previous_overlay.source_start,
                text=previous_overlay.text + replacement_text,
                document_rect=QRectF(previous_overlay.document_rect),
            )
        return PromptProjectionTransientInsertionOverlay(
            source_revision=source_revision,
            committed_source_revision=committed_source_revision,
            source_start=start,
            text=replacement_text,
            document_rect=QRectF(current_caret_document_rect),
        )

    def deletion_targets_insertion_overlay(
        self,
        *,
        start: int,
        end: int,
        freshness_is_stale_safe: bool,
        source_revision: int,
    ) -> bool:
        """Return whether one delete only removes pending inserted overlay text."""

        overlay = self.valid_insertion_overlay(
            freshness_is_stale_safe=freshness_is_stale_safe,
            source_revision=source_revision,
        )
        if overlay is None:
            return False
        overlay_end = overlay.source_start + len(overlay.text)
        return overlay.source_start <= start and end <= overlay_end

    def insertion_overlay_after_deletion(
        self,
        *,
        start: int,
        end: int,
        source_revision: int,
        freshness_is_stale_safe: bool,
        current_source_revision: int,
    ) -> PromptProjectionTransientInsertionOverlay | None:
        """Return remaining pending insertion overlay after a deferred delete."""

        overlay = self.valid_insertion_overlay(
            freshness_is_stale_safe=freshness_is_stale_safe,
            source_revision=current_source_revision,
        )
        if overlay is None:
            return None
        overlay_end = overlay.source_start + len(overlay.text)
        if not (overlay.source_start <= start and end <= overlay_end):
            return None
        relative_start = start - overlay.source_start
        relative_end = end - overlay.source_start
        text = overlay.text[:relative_start] + overlay.text[relative_end:]
        if not text:
            return None
        return PromptProjectionTransientInsertionOverlay(
            source_revision=source_revision,
            committed_source_revision=overlay.committed_source_revision,
            source_start=overlay.source_start,
            text=text,
            document_rect=QRectF(overlay.document_rect),
        )

    def single_character_deletion_overlay(
        self,
        *,
        start: int,
        end: int,
        source_revision: int,
        committed_source_revision: int,
        previous_overlay: PromptProjectionTransientDeletionOverlay | None,
        layout: PromptProjectionLayout,
        viewport_width: float,
        viewport_height: float,
    ) -> PromptProjectionTransientDeletionOverlay | None:
        """Return erase geometry for one deferred single-character deletion."""

        if end != start + 1:
            return None
        return self.deletion_overlay_for_single_character_range(
            start=start,
            end=end,
            source_revision=source_revision,
            committed_source_revision=committed_source_revision,
            previous_overlay=previous_overlay,
            layout=layout,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )

    def fallback_caret_geometry_for_edit(
        self,
        *,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
        source_revision: int,
        committed_source_revision: int,
        current_caret_document_rect: QRectF,
        metrics: PromptProjectionMetrics,
        content_right: float,
        document_margin: float,
        source_line_content_left_inset: float,
        projection_document: PromptProjectionDocument,
        layout: PromptProjectionLayout,
    ) -> PromptProjectionTransientCaretGeometry | None:
        """Return provisional caret geometry while fallback projection is pending."""

        if start is None or end is None or replacement_text is None:
            return None
        if cursor_state.source_position != anchor_state.source_position:
            return None
        base_rect = QRectF(current_caret_document_rect)
        if replacement_text == "\n":
            document_rect = QRectF(
                document_margin + max(0.0, source_line_content_left_inset),
                base_rect.top() + metrics.text_line_height,
                max(1.0, base_rect.width()),
                max(base_rect.height(), metrics.text_line_height),
            )
        elif replacement_text:
            advance = metrics.text_advance(replacement_text)
            document_rect = QRectF(base_rect).translated(advance, 0.0)
            if document_rect.left() > content_right + 0.01:
                document_rect.moveLeft(
                    document_margin + max(0.0, source_line_content_left_inset)
                )
                document_rect.moveTop(base_rect.top() + metrics.text_line_height)
        elif end == start + 1:
            caret_state = projection_document.caret_map.state_for_source_position(start)
            document_rect = layout.cursor_rect(caret_state, scroll_offset=0.0)
        else:
            return None
        return PromptProjectionTransientCaretGeometry(
            source_revision=source_revision,
            cursor_position=cursor_state.source_position,
            anchor_position=anchor_state.source_position,
            committed_source_revision=committed_source_revision,
            document_rect=document_rect,
        )

    def fallback_insertion_overlay_for_edit(
        self,
        *,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
        source_revision: int,
        committed_source_revision: int,
        current_caret_document_rect: QRectF,
        metrics: PromptProjectionMetrics,
        content_right: float,
        document_margin: float,
        source_line_content_left_inset: float,
    ) -> PromptProjectionTransientInsertionOverlay | None:
        """Return provisional inserted text while fallback projection is pending."""

        if (
            start is None
            or end is None
            or start != end
            or replacement_text is None
            or len(replacement_text) != 1
            or replacement_text in {"\n", "\r", "\t"}
        ):
            return None
        document_rect = QRectF(current_caret_document_rect)
        if (
            document_rect.left() + metrics.text_advance(replacement_text)
            > content_right + 0.01
        ):
            document_rect.moveLeft(
                document_margin + max(0.0, source_line_content_left_inset)
            )
            document_rect.moveTop(document_rect.top() + metrics.text_line_height)
        return PromptProjectionTransientInsertionOverlay(
            source_revision=source_revision,
            committed_source_revision=committed_source_revision,
            source_start=start,
            text=replacement_text,
            document_rect=document_rect,
        )

    def fallback_deletion_overlay_for_edit(
        self,
        *,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
        source_revision: int,
        committed_source_revision: int,
        previous_overlay: PromptProjectionTransientDeletionOverlay | None,
        layout: PromptProjectionLayout,
        viewport_width: float,
        viewport_height: float,
    ) -> PromptProjectionTransientDeletionOverlay | None:
        """Return provisional erase geometry while fallback projection is pending."""

        if start is None or end is None or replacement_text != "" or end != start + 1:
            return None
        return self.deletion_overlay_for_single_character_range(
            start=start,
            end=end,
            source_revision=source_revision,
            committed_source_revision=committed_source_revision,
            previous_overlay=previous_overlay,
            layout=layout,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )

    def deletion_overlay_for_single_character_range(
        self,
        *,
        start: int,
        end: int,
        source_revision: int,
        committed_source_revision: int,
        previous_overlay: PromptProjectionTransientDeletionOverlay | None,
        layout: PromptProjectionLayout,
        viewport_width: float,
        viewport_height: float,
    ) -> PromptProjectionTransientDeletionOverlay | None:
        """Return merged erase geometry for one deferred character deletion."""

        fragment_start = start
        fragment_end = end
        source_start = start
        source_end = end
        previous_rects: tuple[QRectF, ...] = ()
        if (
            previous_overlay is not None
            and previous_overlay.committed_source_revision == committed_source_revision
        ):
            previous_rects = previous_overlay.document_rects
            if previous_overlay.source_start == end:
                source_start = start
                source_end = previous_overlay.source_end
            elif previous_overlay.source_start == start:
                fragment_start = previous_overlay.source_end
                fragment_end = previous_overlay.source_end + 1
                source_start = previous_overlay.source_start
                source_end = fragment_end
            else:
                previous_rects = ()
        viewport_rect = QRectF(
            0.0,
            0.0,
            max(layout.content_size().width(), viewport_width),
            max(layout.content_size().height(), viewport_height),
        )
        document_rects = tuple(
            rect
            for rect in layout.source_range_fragments(
                fragment_start,
                fragment_end,
                viewport_rect=viewport_rect,
                scroll_offset=0.0,
            )
            if rect.isValid() and not rect.isEmpty()
        )
        document_rects = (*previous_rects, *document_rects)
        if not document_rects:
            return None
        return PromptProjectionTransientDeletionOverlay(
            source_revision=source_revision,
            committed_source_revision=committed_source_revision,
            source_start=source_start,
            source_end=source_end,
            document_rects=document_rects,
        )

    def insertion_overlay_document_rect(
        self,
        overlay: PromptProjectionTransientInsertionOverlay,
        *,
        metrics: PromptProjectionMetrics,
    ) -> QRectF:
        """Return the document-local paint rect for one insertion overlay."""

        overlay_width = max(1.0, metrics.text_advance(overlay.text))
        document_rect = QRectF(overlay.document_rect)
        return QRectF(
            document_rect.left(),
            document_rect.top(),
            overlay_width,
            max(document_rect.height(), metrics.text_line_height),
        )

    def insertion_overlay_viewport_rect(
        self,
        overlay: PromptProjectionTransientInsertionOverlay,
        *,
        metrics: PromptProjectionMetrics,
        scroll_offset: float,
    ) -> QRectF:
        """Return the viewport-local paint rect for one insertion overlay."""

        return self.insertion_overlay_document_rect(
            overlay,
            metrics=metrics,
        ).translated(0.0, -scroll_offset)

    def insertion_overlay_repaint_rect(
        self,
        *,
        previous_overlay: PromptProjectionTransientInsertionOverlay | None,
        next_overlay: PromptProjectionTransientInsertionOverlay | None,
        metrics: PromptProjectionMetrics,
        scroll_offset: float,
    ) -> QRectF | None:
        """Return viewport-local repaint bounds for an insertion overlay change."""

        repaint_rect: QRectF | None = None
        if previous_overlay is not None:
            repaint_rect = self.insertion_overlay_viewport_rect(
                previous_overlay,
                metrics=metrics,
                scroll_offset=scroll_offset,
            )
        if next_overlay is not None:
            next_rect = self.insertion_overlay_viewport_rect(
                next_overlay,
                metrics=metrics,
                scroll_offset=scroll_offset,
            )
            repaint_rect = (
                next_rect if repaint_rect is None else repaint_rect.united(next_rect)
            )
        if repaint_rect is None:
            return None
        return repaint_rect.adjusted(-3.0, -2.0, 3.0, 2.0)

    def deletion_overlay_viewport_rects(
        self,
        overlay: PromptProjectionTransientDeletionOverlay,
        *,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return viewport-local source-text rects for one deletion overlay."""

        return tuple(
            rect.translated(0.0, -scroll_offset)
            for rect in overlay.document_rects
            if rect.isValid() and not rect.isEmpty()
        )

    def deletion_overlay_erase_rects(
        self,
        overlay: PromptProjectionTransientDeletionOverlay,
        *,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return expanded viewport-local deletion erase bands grouped by row."""

        return merge_same_row_rects(
            tuple(
                rect.adjusted(-3.0, -2.0, 3.0, 2.0)
                for rect in self.deletion_overlay_viewport_rects(
                    overlay,
                    scroll_offset=scroll_offset,
                )
            )
        )

    def deletion_visible_region(
        self,
        overlay: PromptProjectionTransientDeletionOverlay | None,
        *,
        viewport_region: QRegion,
        scroll_offset: float,
    ) -> QRegion | None:
        """Return viewport region where stale projection text may still paint."""

        if overlay is None:
            return None
        visible_region = QRegion(viewport_region)
        for rect in self.deletion_overlay_erase_rects(
            overlay,
            scroll_offset=scroll_offset,
        ):
            visible_region = visible_region.subtracted(QRegion(rect.toAlignedRect()))
        return visible_region

    def deletion_overlay_repaint_rect(
        self,
        *,
        previous_overlay: PromptProjectionTransientDeletionOverlay | None,
        next_overlay: PromptProjectionTransientDeletionOverlay | None,
        scroll_offset: float,
    ) -> QRectF | None:
        """Return viewport-local repaint bounds for a deletion overlay change."""

        repaint_rect: QRectF | None = None
        for overlay in (previous_overlay, next_overlay):
            if overlay is None:
                continue
            for rect in self.deletion_overlay_erase_rects(
                overlay,
                scroll_offset=scroll_offset,
            ):
                repaint_rect = (
                    rect if repaint_rect is None else repaint_rect.united(rect)
                )
        if repaint_rect is None:
            return None
        return repaint_rect.adjusted(-3.0, -2.0, 3.0, 2.0)


__all__ = [
    "PromptProjectionTransientCaretGeometry",
    "PromptProjectionTransientDeletionOverlay",
    "PromptProjectionTransientEditOverlayController",
    "PromptProjectionTransientInsertionOverlay",
]
