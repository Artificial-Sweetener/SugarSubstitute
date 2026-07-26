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

"""Apply bounded hard-line layout edits without invoking canonical fallback."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QSizeF

from .contracts import (
    PromptLayoutDamage,
    PromptLayoutOutcome,
    PromptLayoutOutput,
    PromptLayoutReason,
    PromptLayoutRequest,
)
from .edit_policy import (
    line_index_for_hard_line_delete,
    line_index_for_hard_line_insert,
    plain_edit_changes_local_tag_keep_ranges,
)
from .snapshot_edits import (
    content_right,
    line_inline_fragment_count,
    line_text_fragment_count,
    remap_downstream_lines_after_hard_line_edit,
)
from .line_break_edits import (
    join_plain_lines_after_newline_delete,
    split_plain_line_for_newline_insert,
)
from .models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLayoutSnapshot,
    PromptProjectionLineSnapshot,
)
from .shifted_snapshot import (
    LineCaretRectMapping,
    LineInlineObjectFragmentSequence,
    LineTextFragmentSequence,
    concrete_line_snapshot,
)


class PromptHardLineLayoutEngine:
    """Own validated non-fallback hard-line layout attempts."""

    def apply_hard_line(self, request: PromptLayoutRequest) -> PromptLayoutOutcome:
        """Split or join plain visual lines for one hard-line source edit."""

        previous = request.previous
        edit = request.edit
        if previous is None:
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.MISSING_PREVIOUS_LAYOUT
            )
        if edit is None:
            return PromptLayoutOutcome.rejected(PromptLayoutReason.MISSING_EDIT)
        if (
            previous.configuration.inline_object_renderers
            is not request.configuration.inline_object_renderers
        ):
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.CONFIGURATION_MISMATCH
            )

        previous_document = previous.projection_document
        projection_document = request.projection_document
        source_delta = len(edit.replacement_text) - (edit.end - edit.start)
        projection_delta = (
            projection_document.mapping.projection_length
            - previous_document.mapping.projection_length
        )
        if source_delta not in {-1, 1} or projection_delta != source_delta:
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.UNSUPPORTED_EDIT_DELTA
            )
        if (
            request.prompt_document_view is not None
            and plain_edit_changes_local_tag_keep_ranges(
                previous_document.source_text,
                projection_document.source_text,
                edit_start=edit.start,
                edit_end=edit.end,
                replacement_text=edit.replacement_text,
            )
        ):
            return PromptLayoutOutcome.rejected(PromptLayoutReason.TAG_KEEP_GROUP)
        if edit.replacement_text == "\n" and edit.start == edit.end:
            return self._apply_middle_newline_insert(request)
        if (
            edit.replacement_text == ""
            and edit.end == edit.start + 1
            and previous_document.source_text[edit.start : edit.end] == "\n"
        ):
            return self._apply_middle_newline_delete(request)
        return PromptLayoutOutcome.rejected(PromptLayoutReason.NOT_HARD_LINE_BREAK_EDIT)

    def _apply_middle_newline_insert(
        self,
        request: PromptLayoutRequest,
    ) -> PromptLayoutOutcome:
        """Split one plain visual line around an inserted hard break."""

        previous = request.previous
        edit = request.edit
        if previous is None or edit is None:
            raise AssertionError("validated hard-line requests require previous edit")
        previous_snapshot = previous.snapshot
        line_index = line_index_for_hard_line_insert(
            previous_snapshot.lines,
            edit_start=edit.start,
        )
        if line_index is None:
            return PromptLayoutOutcome.rejected(PromptLayoutReason.DIRTY_LINE_NOT_FOUND)
        previous_line = concrete_line_snapshot(previous_snapshot.lines[line_index])
        if any(
            isinstance(fragment, PromptProjectionInlineObjectFragment)
            for fragment in previous_line.fragments
        ):
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.DIRTY_LINE_HAS_INLINE_OBJECT
            )

        configuration = request.configuration
        content_left = configuration.document_margin + max(
            0.0, configuration.content_left_inset
        )
        split_result = split_plain_line_for_newline_insert(
            previous_line,
            projection_document=request.projection_document,
            edit_start=edit.start,
            first_dirty_projection_position=edit.first_dirty_projection_position,
            content_left=content_left,
            content_right=content_right(
                text_width=configuration.text_width,
                document_margin=configuration.document_margin,
                content_left_inset=configuration.content_left_inset,
            ),
        )
        if split_result is None:
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.LINE_SPLIT_NOT_SUPPORTED
            )
        left_line, right_line = split_result
        line_height_delta = right_line.height
        downstream_lines = remap_downstream_lines_after_hard_line_edit(
            previous_snapshot.lines[line_index + 1 :],
            projection_document=request.projection_document,
            source_delta=1,
            projection_delta=1,
            y_delta=line_height_delta,
        )
        next_lines = (
            tuple(previous_snapshot.lines[:line_index])
            + (left_line, right_line)
            + downstream_lines
        )
        return self._applied_hard_line_outcome(
            request,
            lines=next_lines,
            content_height_delta=line_height_delta,
            line_index=line_index,
        )

    def _apply_middle_newline_delete(
        self,
        request: PromptLayoutRequest,
    ) -> PromptLayoutOutcome:
        """Join two adjacent plain visual lines after deleting a hard break."""

        previous = request.previous
        edit = request.edit
        if previous is None or edit is None:
            raise AssertionError("validated hard-line requests require previous edit")
        previous_snapshot = previous.snapshot
        line_index = line_index_for_hard_line_delete(
            previous_snapshot.lines,
            edit_start=edit.start,
        )
        if line_index is None or line_index + 1 >= len(previous_snapshot.lines):
            return PromptLayoutOutcome.rejected(PromptLayoutReason.DIRTY_LINE_NOT_FOUND)
        first_line = concrete_line_snapshot(previous_snapshot.lines[line_index])
        second_line = concrete_line_snapshot(previous_snapshot.lines[line_index + 1])
        if any(
            isinstance(fragment, PromptProjectionInlineObjectFragment)
            for fragment in first_line.fragments + second_line.fragments
        ):
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.DIRTY_LINE_HAS_INLINE_OBJECT
            )

        configuration = request.configuration
        content_left = configuration.document_margin + max(
            0.0, configuration.content_left_inset
        )
        joined_line = join_plain_lines_after_newline_delete(
            first_line,
            second_line,
            projection_document=request.projection_document,
            edit_start=edit.start,
            content_left=content_left,
            content_right=content_right(
                text_width=configuration.text_width,
                document_margin=configuration.document_margin,
                content_left_inset=configuration.content_left_inset,
            ),
        )
        if joined_line is None:
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.LINE_JOIN_NOT_SUPPORTED
            )
        line_height_delta = -second_line.height
        downstream_lines = remap_downstream_lines_after_hard_line_edit(
            previous_snapshot.lines[line_index + 2 :],
            projection_document=request.projection_document,
            source_delta=-1,
            projection_delta=-1,
            y_delta=line_height_delta,
        )
        next_lines = (
            tuple(previous_snapshot.lines[:line_index])
            + (joined_line,)
            + downstream_lines
        )
        return self._applied_hard_line_outcome(
            request,
            lines=next_lines,
            content_height_delta=line_height_delta,
            line_index=line_index,
        )

    def _applied_hard_line_outcome(
        self,
        request: PromptLayoutRequest,
        *,
        lines: Sequence[PromptProjectionLineSnapshot],
        content_height_delta: float,
        line_index: int,
    ) -> PromptLayoutOutcome:
        """Return the immutable snapshot and bounded damage for a line edit."""

        previous = request.previous
        if previous is None:
            raise AssertionError("hard-line output requires previous layout")
        previous_snapshot = previous.snapshot
        next_snapshot = PromptProjectionLayoutSnapshot(
            content_size=QSizeF(
                previous_snapshot.content_size.width(),
                max(
                    1.0,
                    previous_snapshot.content_size.height() + content_height_delta,
                ),
            ),
            lines=lines,
            text_fragments=LineTextFragmentSequence(
                lines,
                fragment_count=sum(line_text_fragment_count(line) for line in lines),
            ),
            inline_object_fragments=LineInlineObjectFragmentSequence(
                lines,
                fragment_count=sum(line_inline_fragment_count(line) for line in lines),
            ),
            caret_rects_by_projection_position=LineCaretRectMapping(
                lines,
                caret_count=request.projection_document.mapping.projection_length + 1,
            ),
        )
        return PromptLayoutOutcome.applied(
            reason=PromptLayoutReason.HARD_LINE_EDIT,
            output=PromptLayoutOutput(
                projection_document=request.projection_document,
                prompt_document_view=request.prompt_document_view,
                snapshot=next_snapshot,
                configuration=request.configuration,
            ),
            damage=PromptLayoutDamage(
                content_height_changed=True,
                content_height_delta=content_height_delta,
                first_reflowed_line_index=line_index,
                reflowed_line_count=max(1, len(lines) - line_index),
                upstream_line_count=line_index,
            ),
        )
