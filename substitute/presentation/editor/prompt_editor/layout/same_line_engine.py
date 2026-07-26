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

"""Apply bounded same-line layout edits without invoking canonical fallback."""

from __future__ import annotations


from PySide6.QtCore import QSizeF

from .contracts import (
    PromptLayoutDamage,
    PromptLayoutOutcome,
    PromptLayoutOutput,
    PromptLayoutReason,
    PromptLayoutRequest,
)
from .edit_policy import (
    line_index_for_plain_edit,
    plain_edit_changes_local_tag_keep_ranges,
    plain_edit_requires_tag_keep_reflow,
    plain_edit_touches_visual_word_wrap_boundary,
)
from .snapshot_edits import (
    content_right,
    plain_text_run_for_empty_line_insert,
    remap_lines_for_empty_line_plain_insert,
    remap_lines_for_same_line_plain_edit,
    text_fragment_for_empty_line_insert,
)
from .models import (
    PromptProjectionLayoutSnapshot,
    PromptProjectionTextFragment,
)
from .shifted_snapshot import (
    LineCaretRectMapping,
    LineInlineObjectFragmentSequence,
    LineTextFragmentSequence,
)
from .text_shaping import (
    build_edited_text_fragment,
    editable_text_fragment,
)


class PromptSameLineLayoutEngine:
    """Own validated non-fallback same-line layout attempts."""

    def apply_same_line(self, request: PromptLayoutRequest) -> PromptLayoutOutcome:
        """Apply one non-wrapping source-backed edit to a single visual line."""

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
        previous_snapshot = previous.snapshot
        projection_document = request.projection_document
        configuration = request.configuration
        source_delta = len(edit.replacement_text) - (edit.end - edit.start)
        projection_delta = (
            projection_document.mapping.projection_length
            - previous_document.mapping.projection_length
        )
        if (
            source_delta > 1
            or (projection_delta != source_delta and edit.editable_token_id is None)
        ) or (source_delta == 0 and edit.start == edit.end):
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.UNSUPPORTED_EDIT_DELTA
            )
        if "\n" in edit.replacement_text or "\r" in edit.replacement_text:
            return PromptLayoutOutcome.rejected(PromptLayoutReason.NEWLINE_EDIT)

        line_index = line_index_for_plain_edit(
            previous_snapshot.lines,
            edit_start=edit.start,
            edit_end=edit.end,
            replacement_text=edit.replacement_text,
        )
        if line_index is None:
            return PromptLayoutOutcome.rejected(PromptLayoutReason.DIRTY_LINE_NOT_FOUND)
        previous_line = previous_snapshot.lines[line_index]
        tag_keep_ranges_changed = (
            request.prompt_document_view is not None
            and plain_edit_changes_local_tag_keep_ranges(
                previous_document.source_text,
                projection_document.source_text,
                edit_start=edit.start,
                edit_end=edit.end,
                replacement_text=edit.replacement_text,
            )
        )
        affected_fragment = editable_text_fragment(
            previous_line.fragments,
            edit_start=edit.start,
            edit_end=edit.end,
            replacement_text=edit.replacement_text,
            editable_token_id=edit.editable_token_id,
            projection_edit_start=edit.projection_edit_start,
            projection_edit_end=edit.projection_edit_end,
        )
        empty_line_insert_fragment: PromptProjectionTextFragment | None = None
        if affected_fragment is None and edit.replacement_text:
            next_run = plain_text_run_for_empty_line_insert(
                projection_document,
                line=previous_line,
                edit_start=edit.start,
                replacement_text=edit.replacement_text,
            )
            if next_run is not None:
                empty_line_insert_fragment = text_fragment_for_empty_line_insert(
                    previous_line,
                    next_run=next_run,
                    edit_start=edit.start,
                    replacement_text=edit.replacement_text,
                    content_left=(
                        configuration.document_margin
                        + max(0.0, configuration.content_left_inset)
                    ),
                    base_font=configuration.base_font,
                )
        if affected_fragment is None and empty_line_insert_fragment is None:
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.AFFECTED_FRAGMENT_NOT_FOUND
            )

        if affected_fragment is not None:
            next_run = projection_document.run_by_id(affected_fragment.run_id)
            if next_run is None:
                return PromptLayoutOutcome.rejected(
                    PromptLayoutReason.UPDATED_RUN_NOT_FOUND
                )
            next_fragment = build_edited_text_fragment(
                affected_fragment,
                next_run=next_run,
                edit_start=edit.start,
                edit_end=edit.end,
                replacement_text=edit.replacement_text,
                base_font=configuration.base_font,
                projection_edit_start=edit.projection_edit_start,
                projection_edit_end=edit.projection_edit_end,
                projection_replacement_text=edit.projection_replacement_text,
            )
            if next_fragment is None:
                return PromptLayoutOutcome.rejected(
                    PromptLayoutReason.FRAGMENT_EDIT_NOT_SUPPORTED
                )
        else:
            next_fragment = empty_line_insert_fragment
            if next_fragment is None:
                return PromptLayoutOutcome.rejected(
                    PromptLayoutReason.EMPTY_LINE_INSERT_NOT_SUPPORTED
                )

        editable_run = (
            None
            if affected_fragment is None
            else previous_document.run_by_id(affected_fragment.run_id)
        )
        editable_token_stays_in_one_fragment = bool(
            edit.editable_token_id is not None
            and affected_fragment is not None
            and editable_run is not None
            and affected_fragment.projection_start == editable_run.projection_start
            and affected_fragment.projection_end == editable_run.projection_end
        )
        if (
            not editable_token_stays_in_one_fragment
            and plain_edit_touches_visual_word_wrap_boundary(
                previous_snapshot.lines,
                dirty_line_index=line_index,
                line=previous_line,
                next_source_text=projection_document.source_text,
                edit_start=edit.start,
                edit_end=edit.end,
                replacement_text=edit.replacement_text,
                source_delta=source_delta,
            )
        ):
            return PromptLayoutOutcome.deferred(PromptLayoutReason.WORD_WRAP_BOUNDARY)

        width_delta = (
            next_fragment.rect.width()
            if affected_fragment is None
            else next_fragment.rect.width() - affected_fragment.rect.width()
        )
        content_right_edge = content_right(
            text_width=configuration.text_width,
            document_margin=configuration.document_margin,
            content_left_inset=configuration.content_left_inset,
        )
        if (
            edit.replacement_text
            and previous_line.rect.right() + width_delta > content_right_edge + 0.01
        ):
            return PromptLayoutOutcome.deferred(PromptLayoutReason.EDIT_WOULD_WRAP)
        if (
            request.prompt_document_view is not None
            and plain_edit_requires_tag_keep_reflow(
                request.prompt_document_view,
                previous_source_text=previous_document.source_text,
                lines=previous_snapshot.lines,
                line=previous_line,
                line_index=line_index,
                edit_start=edit.start,
                edit_end=edit.end,
                replacement_text=edit.replacement_text,
                source_delta=source_delta,
                width_delta=width_delta,
                content_right=content_right_edge,
                tag_keep_ranges_changed=tag_keep_ranges_changed,
            )
        ):
            return PromptLayoutOutcome.rejected(PromptLayoutReason.TAG_KEEP_GROUP)

        if affected_fragment is None:
            next_lines = remap_lines_for_empty_line_plain_insert(
                previous_snapshot.lines,
                projection_document=projection_document,
                dirty_line_index=line_index,
                next_fragment=next_fragment,
                edit_start=edit.start,
                edit_end=edit.end,
                source_delta=source_delta,
                projection_delta=projection_delta,
            )
        else:
            next_lines = remap_lines_for_same_line_plain_edit(
                previous_snapshot.lines,
                projection_document=projection_document,
                dirty_line_index=line_index,
                affected_fragment=affected_fragment,
                next_fragment=next_fragment,
                edit_start=edit.start,
                edit_end=edit.end,
                source_delta=source_delta,
                projection_delta=projection_delta,
                width_delta=width_delta,
            )
        next_snapshot = PromptProjectionLayoutSnapshot(
            content_size=QSizeF(previous_snapshot.content_size),
            lines=next_lines,
            text_fragments=LineTextFragmentSequence(
                next_lines,
                fragment_count=(
                    len(previous_snapshot.text_fragments)
                    + (1 if affected_fragment is None else 0)
                ),
            ),
            inline_object_fragments=LineInlineObjectFragmentSequence(
                next_lines,
                fragment_count=len(previous_snapshot.inline_object_fragments),
            ),
            caret_rects_by_projection_position=LineCaretRectMapping(
                next_lines,
                caret_count=max(
                    0,
                    len(previous_snapshot.caret_rects_by_projection_position)
                    + projection_delta,
                ),
            ),
        )
        return PromptLayoutOutcome.applied(
            reason=PromptLayoutReason.SAME_LINE_EDIT,
            output=PromptLayoutOutput(
                projection_document=projection_document,
                prompt_document_view=request.prompt_document_view,
                snapshot=next_snapshot,
                configuration=configuration,
            ),
            damage=PromptLayoutDamage(
                content_height_changed=False,
                content_height_delta=0.0,
                first_reflowed_line_index=line_index,
                reflowed_line_count=1,
                upstream_line_count=line_index,
            ),
        )
