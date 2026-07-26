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

"""Build conservative source-local projection-document edits."""

from __future__ import annotations

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.editing.region_structure_edits import (
    region_structure_edit_requires_rebuild,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)

from .incremental_edit_contracts import (
    PromptProjectionIncrementalDocumentResult,
    PromptProjectionIncrementalEdit,
)
from .plain_text_document_remapper import apply_plain_text_document_edit
from .plain_text_edit_policy import (
    edit_intersects_syntax_span,
    edit_intersects_token,
    plain_text_edit_is_supported,
    projection_position_for_source_boundary,
    source_backed_plain_text_run_for_edit,
)
from .scene_incremental_editor import PromptSceneProjectionIncrementalEditor
from .session import PromptProjectionSession


class PromptPlainTextDocumentEditor:
    """Build supported source-local projection documents."""

    def __init__(self) -> None:
        """Initialize the scene-title mechanism and rejection evidence."""

        self.last_rejection_reason = ""
        self._scene_editor = PromptSceneProjectionIncrementalEditor()

    def try_build_plain_text_edit(
        self,
        edit: PromptProjectionIncrementalEdit,
        *,
        previous_document: PromptProjectionDocument,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        display_mode: PromptProjectionDisplayMode,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
    ) -> PromptProjectionIncrementalDocumentResult | None:
        """Return an incremental projection document for a safe plain edit."""

        del active_span_range, decoration_accent_ranges, session
        self.last_rejection_reason = ""
        if display_mode is not PromptProjectionDisplayMode.PROJECTED:
            return self._reject("display_mode_not_projected")
        if previous_document.source_text != edit.previous_source_text:
            return self._reject("previous_source_mismatch")
        if document_view.source_text != edit.next_source_text:
            return self._reject("document_view_source_mismatch")
        if (
            edit.previous_source_text[: edit.start]
            + edit.replacement_text
            + edit.previous_source_text[edit.end :]
            != edit.next_source_text
        ):
            return self._reject("edit_text_mismatch")
        if region_structure_edit_requires_rebuild(
            edit.previous_source_text,
            edit.next_source_text,
            previous_document.region_structure,
            start=edit.start,
            end=edit.end,
        ):
            return self._reject("region_structure_topology_changed")
        if not plain_text_edit_is_supported(edit):
            return self._reject("unsupported_plain_text_incremental_edit")

        edited_run = source_backed_plain_text_run_for_edit(
            edit,
            previous_document.runs,
        )
        edited_scene_run = self._scene_editor.editable_title_run(
            previous_document=previous_document,
            start=edit.start,
            end=edit.end,
            replacement_text=edit.replacement_text,
        )
        if edited_scene_run is not None:
            edited_run = edited_scene_run
        editable_token_id = (
            None if edited_scene_run is None else edited_scene_run.token_id
        )
        if edit_intersects_token(
            edit,
            previous_document.tokens,
            editable_token_id=editable_token_id,
        ):
            return self._reject("edit_intersects_token")
        if edit_intersects_syntax_span(edit, render_plan.syntax_spans):
            return self._reject("edit_intersects_syntax_span")
        if edited_run is None:
            return self._reject("no_source_backed_plain_text_run")
        if (
            edit.replacement_text == ""
            and len(edited_run.display_text) <= edit.end - edit.start
        ):
            return self._reject("delete_would_empty_run")

        first_dirty_projection_position = projection_position_for_source_boundary(
            edited_run,
            edit.start,
        )
        if (
            first_dirty_projection_position is None
            and edited_scene_run is not None
            and edit.start >= edited_scene_run.source_end
        ):
            first_dirty_projection_position = edited_scene_run.projection_end
        if first_dirty_projection_position is None:
            return self._reject("source_boundary_not_projected")

        try:
            projection_document = apply_plain_text_document_edit(
                edit,
                previous_document=previous_document,
                region_structure=document_view.region_structure,
                edited_run=edited_run,
                first_dirty_projection_position=first_dirty_projection_position,
                editable_token_id=editable_token_id,
            )
        except ValueError:
            return self._reject("invalid_incremental_projection_document")
        if editable_token_id is not None:
            assert edited_scene_run is not None
            scene_result = self._scene_editor.reconcile_document(
                projection_document,
                edited_token_id=editable_token_id,
                previous_visible_text=edited_scene_run.display_text,
                scene_error_keys=scene_error_keys,
            )
            if scene_result is None:
                return self._reject("scene_title_edit_requires_canonical_projection")
            projection_document = scene_result.document
            projection_edit_start = scene_result.projection_start
            projection_edit_end = scene_result.projection_end
            projection_replacement_text = scene_result.projection_replacement_text
        else:
            projection_edit_start = first_dirty_projection_position
            projection_edit_end = first_dirty_projection_position + (
                edit.end - edit.start
            )
            projection_replacement_text = edit.replacement_text
        return PromptProjectionIncrementalDocumentResult(
            projection_document=projection_document,
            first_dirty_source_position=edit.start,
            first_dirty_projection_position=first_dirty_projection_position,
            reason="plain_text_incremental",
            edited_token_id=editable_token_id,
            projection_edit_start=projection_edit_start,
            projection_edit_end=projection_edit_end,
            projection_replacement_text=projection_replacement_text,
        )

    def _reject(
        self,
        reason: str,
    ) -> PromptProjectionIncrementalDocumentResult | None:
        """Record one rejected incremental edit attempt."""

        self.last_rejection_reason = reason
        return None


__all__ = ["PromptPlainTextDocumentEditor"]
