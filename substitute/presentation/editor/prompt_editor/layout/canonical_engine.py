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

"""Build canonical prompt layout snapshots and bounded recovery windows."""

from __future__ import annotations

from typing import Protocol

from .canonical_builder import PromptProjectionLineLayoutBuilder
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
)
from .canonical_edit_window import (
    caret_hosted_reflow_start_line_index,
    line_matches_shifted_plain_edit,
    snapshot_with_rebuilt_plain_edit_window,
)
from .snapshot_edits import remap_source_position_for_layout
from .models import PromptProjectionLineSnapshot
from .reflow_scope import reflow_edit_including_fragment_identity_changes
from .reused_semantics import (
    PromptReusedLineSemanticResolver,
    reusable_suffix_semantics_by_line,
)
from ..projection.tokens import PromptProjectionInlineObjectRendererRegistry


class PromptLineReuseMismatchObserver(Protocol):
    """Observe rejected suffix candidates only when diagnostics are enabled."""

    def __call__(
        self,
        next_line: PromptProjectionLineSnapshot,
        previous_line: PromptProjectionLineSnapshot,
        *,
        source_delta: int,
        projection_delta: int,
    ) -> None:
        """Record one failed candidate without changing engine behavior."""


class PromptCanonicalLayoutEngine:
    """Own full layout and deterministic bounded canonical recovery."""

    def __init__(
        self,
        inline_object_renderers: PromptProjectionInlineObjectRendererRegistry,
    ) -> None:
        """Create the engine with the renderer-backed measurement cache."""

        self._inline_object_renderers = inline_object_renderers
        self._line_builder = PromptProjectionLineLayoutBuilder(
            self._inline_object_renderers
        )
        self._reflow_mismatch_observer: PromptLineReuseMismatchObserver | None = None

    def set_reflow_mismatch_observer(
        self,
        observer: PromptLineReuseMismatchObserver | None,
    ) -> None:
        """Install diagnostic observation outside successful convergence paths."""

        self._reflow_mismatch_observer = observer

    def build(self, request: PromptLayoutRequest) -> PromptLayoutOutcome:
        """Build a complete canonical snapshot for one request."""

        if (
            request.configuration.inline_object_renderers
            is not self._inline_object_renderers
        ):
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.CONFIGURATION_MISMATCH
            )
        configuration = request.configuration
        snapshot = self._line_builder.build_snapshot(
            request.projection_document,
            wrap_width=configuration.text_width,
            base_font=configuration.base_font,
            document_margin=configuration.document_margin,
            content_left_inset=configuration.content_left_inset,
            prompt_document_view=request.prompt_document_view,
            metrics=configuration.metrics,
        )
        previous_snapshot = (
            None if request.previous is None else request.previous.snapshot
        )
        previous_height = (
            snapshot.content_size.height()
            if previous_snapshot is None
            else previous_snapshot.content_size.height()
        )
        damage = PromptLayoutDamage(
            content_height_changed=(
                previous_snapshot is None
                or abs(snapshot.content_size.height() - previous_height) > 0.01
            ),
            content_height_delta=snapshot.content_size.height() - previous_height,
            first_reflowed_line_index=0,
            reflowed_line_count=max(1, len(snapshot.lines)),
            upstream_line_count=0,
        )
        return PromptLayoutOutcome.applied(
            reason=PromptLayoutReason.CANONICAL_BUILD,
            output=PromptLayoutOutput(
                projection_document=request.projection_document,
                prompt_document_view=request.prompt_document_view,
                snapshot=snapshot,
                configuration=configuration,
            ),
            damage=damage,
        )

    def reflow(self, request: PromptLayoutRequest) -> PromptLayoutOutcome:
        """Rebuild a bounded edit window through deterministic suffix convergence."""

        previous = request.previous
        edit = request.edit
        prompt_document_view = request.prompt_document_view
        if previous is None:
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.MISSING_PREVIOUS_LAYOUT
            )
        if edit is None:
            return PromptLayoutOutcome.rejected(PromptLayoutReason.MISSING_EDIT)
        if prompt_document_view is None:
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.MISSING_DOCUMENT_VIEW
            )
        if (
            request.configuration.inline_object_renderers
            is not self._inline_object_renderers
        ):
            return PromptLayoutOutcome.rejected(
                PromptLayoutReason.CONFIGURATION_MISMATCH
            )

        previous_document = previous.projection_document
        previous_snapshot = previous.snapshot
        projection_document = request.projection_document
        configuration = request.configuration
        reflow_edit = reflow_edit_including_fragment_identity_changes(
            previous_document,
            projection_document,
            start=edit.start,
            end=edit.end,
            replacement_text=edit.replacement_text,
        )
        edit_start = reflow_edit.start
        edit_end = reflow_edit.end
        replacement_text = reflow_edit.replacement_text
        source_delta = len(replacement_text) - (edit_end - edit_start)
        projection_delta = (
            projection_document.mapping.projection_length
            - previous_document.mapping.projection_length
        )
        dirty_line_index = line_index_for_plain_edit(
            previous_snapshot.lines,
            edit_start=edit_start,
            edit_end=edit_end,
            replacement_text=replacement_text,
        )
        first_line = 0 if dirty_line_index is None else dirty_line_index
        if first_line > 0 and plain_edit_changes_local_tag_keep_ranges(
            previous_document.source_text,
            projection_document.source_text,
            edit_start=edit_start,
            edit_end=edit_end,
            replacement_text=replacement_text,
        ):
            first_line -= 1
        first_line = caret_hosted_reflow_start_line_index(
            previous_snapshot.lines,
            first_line,
        )
        dirty_line = (
            previous_snapshot.lines[first_line] if previous_snapshot.lines else None
        )
        reflow_source_start = 0 if dirty_line is None else dirty_line.source_start
        reflow_projection_start = (
            0
            if dirty_line is None or not dirty_line.caret_stops
            else dirty_line.caret_stops[0].projection_position
        )
        reflow_line_top = (
            configuration.metrics.initial_line_top()
            if dirty_line is None
            else dirty_line.top
        )
        reusable_lines = {
            line.source_start + source_delta: line_index
            for line_index, line in enumerate(previous_snapshot.lines)
            if line.source_start >= edit_end
        }
        semantic_resolver = PromptReusedLineSemanticResolver(projection_document)
        reusable_semantics = reusable_suffix_semantics_by_line(
            previous_snapshot.lines,
            semantic_resolver,
            projection_delta=projection_delta,
        )

        def reusable_previous_line_index(
            line: PromptProjectionLineSnapshot,
        ) -> int | None:
            """Return the matching previous line after deterministic convergence."""

            previous_line_index = reusable_lines.get(line.source_start)
            if previous_line_index is None:
                return None
            previous_line = previous_snapshot.lines[previous_line_index]
            if not reusable_semantics[previous_line_index]:
                return None
            if not line_matches_shifted_plain_edit(
                line,
                previous_line,
                source_delta=source_delta,
                projection_delta=projection_delta,
            ):
                observer = self._reflow_mismatch_observer
                if observer is not None:
                    observer(
                        line,
                        previous_line,
                        source_delta=source_delta,
                        projection_delta=projection_delta,
                    )
                return None
            return previous_line_index

        source_coordinates_are_unchanged = (
            source_delta == 0
            and previous_document.source_text == projection_document.source_text
        )
        probe_line_span = (
            max(2, len(previous_snapshot.lines))
            if source_coordinates_are_unchanged
            else 2
        )
        while True:
            if previous_snapshot.lines:
                probe_line_index = min(
                    len(previous_snapshot.lines) - 1,
                    first_line + probe_line_span,
                )
                guard_line_index = min(
                    len(previous_snapshot.lines) - 1,
                    probe_line_index + 1,
                )
                source_limit = remap_source_position_for_layout(
                    previous_snapshot.lines[guard_line_index].source_end,
                    edit_start=edit_start,
                    edit_end=edit_end,
                    delta=source_delta,
                )
                source_limit = min(
                    len(projection_document.source_text),
                    max(edit_start + len(replacement_text), source_limit),
                )
            else:
                source_limit = len(projection_document.source_text)
            build_result = self._line_builder.build_snapshot_until_reusable_suffix(
                projection_document,
                wrap_width=configuration.text_width,
                base_font=configuration.base_font,
                document_margin=configuration.document_margin,
                content_left_inset=configuration.content_left_inset,
                prompt_document_view=prompt_document_view,
                metrics=configuration.metrics,
                line_reuse_probe=reusable_previous_line_index,
                source_start=reflow_source_start,
                projection_start=reflow_projection_start,
                line_top=reflow_line_top,
                source_limit=source_limit,
            )
            if (
                build_result.reusable_previous_line_index is not None
                or not build_result.source_limited
            ):
                break
            probe_line_span *= 2

        partial_snapshot = build_result.snapshot
        next_snapshot = snapshot_with_rebuilt_plain_edit_window(
            partial_snapshot,
            previous_snapshot=previous_snapshot,
            first_rebuilt_line_index=first_line,
            previous_match_index=build_result.reusable_previous_line_index,
            source_delta=source_delta,
            projection_delta=projection_delta,
            semantic_resolver=semantic_resolver,
        )
        height_delta = (
            next_snapshot.content_size.height()
            - previous_snapshot.content_size.height()
        )
        return PromptLayoutOutcome.applied(
            reason=PromptLayoutReason.CANONICAL_REFLOW,
            output=PromptLayoutOutput(
                projection_document=projection_document,
                prompt_document_view=prompt_document_view,
                snapshot=next_snapshot,
                configuration=configuration,
            ),
            damage=PromptLayoutDamage(
                content_height_changed=abs(height_delta) > 0.01,
                content_height_delta=height_delta,
                first_reflowed_line_index=first_line,
                reflowed_line_count=max(1, len(partial_snapshot.lines)),
                upstream_line_count=first_line,
            ),
        )
