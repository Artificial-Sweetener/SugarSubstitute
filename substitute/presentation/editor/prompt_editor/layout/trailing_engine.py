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

"""Apply bounded trailing layout edits without invoking canonical fallback."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QRectF, QSizeF

from .contracts import (
    PromptLayoutDamage,
    PromptLayoutOutcome,
    PromptLayoutOutput,
    PromptLayoutReason,
    PromptLayoutRequest,
)
from .edit_policy import (
    plain_edit_changes_local_tag_keep_ranges,
)
from .models import (
    PromptProjectionLayoutSnapshot,
    PromptProjectionLineCaretStopSnapshot,
    PromptProjectionLineSnapshot,
)
from .shifted_snapshot import (
    LineCaretRectMapping,
    concrete_line_snapshot,
    concrete_text_fragment,
)
from .text_shaping import (
    text_boundary_offsets,
)


class PromptTrailingLayoutEngine:
    """Own validated non-fallback trailing layout attempts."""

    def apply_trailing_plain_delete(
        self,
        request: PromptLayoutRequest,
    ) -> PromptLayoutOutcome:
        """Apply a one-character trailing plain-text delete without reflow."""

        previous = request.previous
        if previous is None:
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.MISSING_PREVIOUS_LAYOUT
            )
        previous_document = previous.projection_document
        previous_snapshot = previous.snapshot
        projection_document = request.projection_document
        previous_projection_length = previous_document.mapping.projection_length
        next_projection_length = projection_document.mapping.projection_length
        previous_source_length = len(previous_document.source_text)
        next_source_length = len(projection_document.source_text)
        if (
            next_source_length != previous_source_length - 1
            or next_projection_length != previous_projection_length - 1
            or projection_document.source_text
            != previous_document.source_text[:next_source_length]
            or projection_document.projection_text
            != previous_document.projection_text[:next_projection_length]
            or not previous_snapshot.lines
            or not previous_snapshot.text_fragments
        ):
            return self._trailing_rejected()

        previous_fragment = previous_snapshot.text_fragments[-1]
        previous_line = previous_snapshot.lines[-1]
        if (
            previous_fragment.projection_end != previous_projection_length
            or previous_fragment.source_positions[-1] != previous_source_length
            or not previous_fragment.text
            or not previous_line.fragments
            or previous_line.fragments[-1] != previous_fragment
        ):
            return self._trailing_rejected()

        previous_fragment = concrete_text_fragment(previous_fragment)
        previous_line = concrete_line_snapshot(previous_line)
        next_fragment_text = previous_fragment.text[:-1]
        next_fragment_source_positions = tuple(previous_fragment.source_positions[:-1])
        next_fragment_boundary_offsets = previous_fragment.boundary_offsets[:-1]
        if not next_fragment_boundary_offsets:
            return self._trailing_rejected()

        next_fragment_rect = QRectF(previous_fragment.rect)
        next_fragment_rect.setWidth(max(1.0, next_fragment_boundary_offsets[-1]))
        next_fragment = replace(
            previous_fragment,
            projection_end=next_projection_length,
            text=next_fragment_text,
            source_positions=next_fragment_source_positions,
            rect=next_fragment_rect,
            boundary_offsets=next_fragment_boundary_offsets,
        )
        if next_fragment_text:
            next_line_fragments = previous_line.fragments[:-1] + (next_fragment,)
            next_text_fragments = tuple(previous_snapshot.text_fragments[:-1]) + (
                next_fragment,
            )
        else:
            next_line_fragments = previous_line.fragments[:-1]
            next_text_fragments = tuple(previous_snapshot.text_fragments[:-1])

        next_line = replace(
            previous_line,
            source_end=min(previous_line.source_end, next_source_length),
            source_content_end=min(
                previous_line.source_content_end,
                next_source_length,
            ),
            fragments=next_line_fragments,
            caret_stops=tuple(
                stop
                for stop in previous_line.caret_stops
                if stop.projection_position <= next_projection_length
            ),
        )
        next_lines = tuple(previous_snapshot.lines[:-1]) + (next_line,)
        return self._trailing_applied(
            request,
            snapshot=PromptProjectionLayoutSnapshot(
                content_size=QSizeF(previous_snapshot.content_size),
                lines=next_lines,
                text_fragments=next_text_fragments,
                inline_object_fragments=previous_snapshot.inline_object_fragments,
                caret_rects_by_projection_position=LineCaretRectMapping(
                    next_lines,
                    caret_count=next_projection_length + 1,
                ),
            ),
            reason=PromptLayoutReason.TRAILING_PLAIN_DELETE,
            first_line_index=len(next_lines) - 1,
        )

    def apply_trailing_newline_delete(
        self,
        request: PromptLayoutRequest,
    ) -> PromptLayoutOutcome:
        """Delete a trailing hard line without full layout construction."""

        previous = request.previous
        if previous is None:
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.MISSING_PREVIOUS_LAYOUT
            )
        previous_document = previous.projection_document
        previous_snapshot = previous.snapshot
        projection_document = request.projection_document
        previous_projection_length = previous_document.mapping.projection_length
        next_projection_length = projection_document.mapping.projection_length
        previous_source_length = len(previous_document.source_text)
        next_source_length = len(projection_document.source_text)
        if (
            next_source_length != previous_source_length - 1
            or next_projection_length != previous_projection_length - 1
            or not previous_document.source_text.endswith("\n")
            or projection_document.source_text != previous_document.source_text[:-1]
            or projection_document.projection_text
            != previous_document.projection_text[:-1]
            or len(previous_snapshot.lines) < 2
        ):
            return self._trailing_rejected()

        previous_content_line = previous_snapshot.lines[-2]
        previous_empty_line = previous_snapshot.lines[-1]
        if (
            previous_empty_line.fragments
            or previous_empty_line.line_break_start is not None
            or previous_empty_line.source_start != previous_source_length
            or previous_empty_line.source_end != previous_source_length
            or previous_content_line.line_break_start != next_source_length
            or previous_content_line.line_break_end != previous_source_length
        ):
            return self._trailing_rejected()

        previous_content_line = concrete_line_snapshot(previous_content_line)
        next_content_line = replace(
            previous_content_line,
            source_end=next_source_length,
            line_break_start=None,
            line_break_end=None,
            caret_stops=tuple(
                stop
                for stop in previous_content_line.caret_stops
                if stop.projection_position <= next_projection_length
            ),
        )
        last_stop = (
            next_content_line.caret_stops[-1] if next_content_line.caret_stops else None
        )
        if last_stop is not None and all(
            stop.projection_position != next_projection_length
            for stop in next_content_line.caret_stops
        ):
            next_content_line = replace(
                next_content_line,
                caret_stops=next_content_line.caret_stops
                + (
                    PromptProjectionLineCaretStopSnapshot(
                        projection_position=next_projection_length,
                        rect=QRectF(last_stop.rect),
                    ),
                ),
            )
        next_lines = tuple(previous_snapshot.lines[:-2]) + (next_content_line,)
        next_content_height = max(
            1.0,
            previous_snapshot.content_size.height() - previous_empty_line.height,
        )
        return self._trailing_applied(
            request,
            snapshot=PromptProjectionLayoutSnapshot(
                content_size=QSizeF(
                    previous_snapshot.content_size.width(),
                    next_content_height,
                ),
                lines=next_lines,
                text_fragments=previous_snapshot.text_fragments,
                inline_object_fragments=previous_snapshot.inline_object_fragments,
                caret_rects_by_projection_position=LineCaretRectMapping(
                    next_lines,
                    caret_count=next_projection_length + 1,
                ),
            ),
            reason=PromptLayoutReason.TRAILING_NEWLINE_DELETE,
            first_line_index=max(0, len(next_lines) - 1),
            content_height_delta=-previous_empty_line.height,
        )

    def apply_trailing_plain_insert(
        self,
        request: PromptLayoutRequest,
    ) -> PromptLayoutOutcome:
        """Append plain text when the final fragment remains unwrapped."""

        previous = request.previous
        if previous is None:
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.MISSING_PREVIOUS_LAYOUT
            )
        previous_document = previous.projection_document
        previous_snapshot = previous.snapshot
        projection_document = request.projection_document
        previous_projection_length = previous_document.mapping.projection_length
        next_projection_length = projection_document.mapping.projection_length
        previous_source_length = len(previous_document.source_text)
        next_source_length = len(projection_document.source_text)
        appended_length = next_source_length - previous_source_length
        if (
            appended_length <= 0
            or next_projection_length != previous_projection_length + appended_length
            or projection_document.source_text[:previous_source_length]
            != previous_document.source_text
            or projection_document.projection_text[:previous_projection_length]
            != previous_document.projection_text
            or not previous_snapshot.lines
            or not previous_snapshot.text_fragments
        ):
            return self._trailing_rejected()

        previous_fragment = previous_snapshot.text_fragments[-1]
        previous_line = previous_snapshot.lines[-1]
        if (
            previous_fragment.projection_end != previous_projection_length
            or previous_fragment.source_positions[-1] != previous_source_length
            or not previous_line.fragments
            or previous_line.fragments[-1] != previous_fragment
        ):
            return self._trailing_rejected()

        previous_fragment = concrete_text_fragment(previous_fragment)
        previous_line = concrete_line_snapshot(previous_line)
        appended_text = projection_document.projection_text[previous_projection_length:]
        if len(appended_text) != appended_length or any(
            character in {"\n", "\r"} for character in appended_text
        ):
            return self._trailing_rejected()
        if (
            request.prompt_document_view is not None
            and plain_edit_changes_local_tag_keep_ranges(
                previous_document.source_text,
                projection_document.source_text,
                edit_start=previous_source_length,
                edit_end=previous_source_length,
                replacement_text=appended_text,
            )
        ):
            return self._trailing_rejected()

        configuration = request.configuration
        next_fragment_text = previous_fragment.text + appended_text
        next_fragment_source_positions = tuple(
            previous_fragment.source_positions
        ) + tuple(range(previous_source_length + 1, next_source_length + 1))
        next_fragment_boundary_offsets = text_boundary_offsets(
            next_fragment_text,
            configuration.base_font,
        )
        if len(next_fragment_boundary_offsets) != len(next_fragment_text) + 1:
            return self._trailing_rejected()
        next_width = next_fragment_boundary_offsets[-1]
        content_right_edge = (
            configuration.document_margin
            + max(0.0, configuration.content_left_inset)
            + max(
                1.0,
                configuration.text_width
                - (configuration.document_margin * 2.0)
                - max(0.0, configuration.content_left_inset),
            )
        )
        if previous_fragment.rect.left() + next_width > content_right_edge + 0.01:
            return self._trailing_rejected()

        next_fragment_rect = QRectF(previous_fragment.rect)
        next_fragment_rect.setWidth(max(1.0, next_width))
        next_fragment = replace(
            previous_fragment,
            projection_end=next_projection_length,
            text=next_fragment_text,
            source_positions=next_fragment_source_positions,
            rect=next_fragment_rect,
            boundary_offsets=next_fragment_boundary_offsets,
        )
        first_appended_boundary_index = len(previous_fragment.text) + 1
        appended_caret_stops = tuple(
            PromptProjectionLineCaretStopSnapshot(
                projection_position=(
                    previous_fragment.projection_start + boundary_index
                ),
                rect=QRectF(
                    previous_fragment.rect.left()
                    + next_fragment_boundary_offsets[boundary_index],
                    previous_line.top,
                    1.0,
                    previous_line.height,
                ),
            )
            for boundary_index in range(
                first_appended_boundary_index,
                len(next_fragment_boundary_offsets),
            )
        )
        next_line = replace(
            previous_line,
            source_end=next_source_length,
            source_content_end=next_source_length,
            fragments=previous_line.fragments[:-1] + (next_fragment,),
            caret_stops=previous_line.caret_stops + appended_caret_stops,
        )
        next_lines = tuple(previous_snapshot.lines[:-1]) + (next_line,)
        return self._trailing_applied(
            request,
            snapshot=PromptProjectionLayoutSnapshot(
                content_size=QSizeF(previous_snapshot.content_size),
                lines=next_lines,
                text_fragments=tuple(previous_snapshot.text_fragments[:-1])
                + (next_fragment,),
                inline_object_fragments=previous_snapshot.inline_object_fragments,
                caret_rects_by_projection_position=LineCaretRectMapping(
                    next_lines,
                    caret_count=next_projection_length + 1,
                ),
            ),
            reason=PromptLayoutReason.TRAILING_PLAIN_INSERT,
            first_line_index=len(next_lines) - 1,
        )

    def apply_trailing_newline_insert(
        self,
        request: PromptLayoutRequest,
    ) -> PromptLayoutOutcome:
        """Append a final empty hard line without full layout construction."""

        previous = request.previous
        if previous is None:
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.MISSING_PREVIOUS_LAYOUT
            )
        previous_document = previous.projection_document
        previous_snapshot = previous.snapshot
        projection_document = request.projection_document
        previous_projection_length = previous_document.mapping.projection_length
        next_projection_length = projection_document.mapping.projection_length
        previous_source_length = len(previous_document.source_text)
        next_source_length = len(projection_document.source_text)
        if (
            next_source_length != previous_source_length + 1
            or next_projection_length != previous_projection_length + 1
            or projection_document.source_text != previous_document.source_text + "\n"
            or projection_document.projection_text
            != previous_document.projection_text + "\n"
            or not previous_snapshot.lines
        ):
            return self._trailing_rejected()

        previous_line = concrete_line_snapshot(previous_snapshot.lines[-1])
        metrics = request.configuration.metrics
        base_line_height = metrics.text_line_height
        next_line_top = previous_line.top + previous_line.height
        next_line = PromptProjectionLineSnapshot(
            top=next_line_top,
            height=base_line_height,
            source_start=next_source_length,
            source_end=next_source_length,
            source_content_start=next_source_length,
            source_content_end=next_source_length,
            line_break_start=None,
            line_break_end=None,
            fragments=(),
            caret_stops=(
                PromptProjectionLineCaretStopSnapshot(
                    projection_position=next_projection_length,
                    rect=QRectF(
                        metrics.caret_rect(
                            x_left=metrics.content_left,
                            row_top=next_line_top,
                            row_height=base_line_height,
                        )
                    ),
                ),
            ),
        )
        next_previous_line = replace(
            previous_line,
            source_end=next_source_length,
            line_break_start=previous_source_length,
            line_break_end=next_source_length,
        )
        next_lines = tuple(previous_snapshot.lines[:-1]) + (
            next_previous_line,
            next_line,
        )
        return self._trailing_applied(
            request,
            snapshot=PromptProjectionLayoutSnapshot(
                content_size=QSizeF(
                    previous_snapshot.content_size.width(),
                    previous_snapshot.content_size.height() + base_line_height,
                ),
                lines=next_lines,
                text_fragments=previous_snapshot.text_fragments,
                inline_object_fragments=previous_snapshot.inline_object_fragments,
                caret_rects_by_projection_position=LineCaretRectMapping(
                    next_lines,
                    caret_count=next_projection_length + 1,
                ),
            ),
            reason=PromptLayoutReason.TRAILING_NEWLINE_INSERT,
            first_line_index=len(next_lines) - 2,
            content_height_delta=base_line_height,
        )

    @staticmethod
    def _trailing_rejected() -> PromptLayoutOutcome:
        """Return the common inert result for an unsupported trailing edit."""

        return PromptLayoutOutcome.rejected(
            PromptLayoutReason.TRAILING_EDIT_NOT_SUPPORTED
        )

    @staticmethod
    def _trailing_applied(
        request: PromptLayoutRequest,
        *,
        snapshot: PromptProjectionLayoutSnapshot,
        reason: PromptLayoutReason,
        first_line_index: int,
        content_height_delta: float = 0.0,
    ) -> PromptLayoutOutcome:
        """Publish one trailing snapshot with bounded line and height damage."""

        return PromptLayoutOutcome.applied(
            reason=reason,
            output=PromptLayoutOutput(
                projection_document=request.projection_document,
                prompt_document_view=request.prompt_document_view,
                snapshot=snapshot,
                configuration=request.configuration,
            ),
            damage=PromptLayoutDamage(
                content_height_changed=abs(content_height_delta) > 0.01,
                content_height_delta=content_height_delta,
                first_reflowed_line_index=first_line_index,
                reflowed_line_count=1,
                upstream_line_count=first_line_index,
            ),
        )
