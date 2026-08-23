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

"""Connect mounted reorder previews to the production editor surface."""

from __future__ import annotations

from typing import Any, cast


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfileService,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.overlays import (
    SegmentReorderOverlay,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview import (
    PromptReorderPreviewState,
    PromptReorderProjectionSnapshot,
)

from .gateway_support import _EmptyPromptWildcardCatalogGateway


def _connect_preview_sync(
    editor: PromptEditor,
    overlay: SegmentReorderOverlay,
    *,
    document_service: PromptDocumentService,
    syntax_service: PromptSyntaxService,
    syntax_profile: object,
    document_view: PromptDocumentView,
) -> None:
    """Mirror the controller's preview-state synchronization for direct overlay tests."""

    def _sync_preview_state() -> None:
        """Push one overlay preview update through the editor surface."""

        preview_facts = overlay.preview_build_facts.snapshot()
        preview_layout_view = preview_facts.preview_layout_view
        base_drag_layout_view = preview_facts.base_drag_layout_view
        ordered_chip_indices = preview_facts.ordered_chip_indices
        if preview_layout_view is None and base_drag_layout_view is None:
            overlay.set_preview_snapshot(
                None,
                base_drag_snapshot=None,
                ordered_chip_indices=ordered_chip_indices,
            )
            editor.clear_reorder_preview_state()
            return
        if preview_layout_view is None:
            current_layout_view = overlay.current_layout_view()
            assert base_drag_layout_view is not None
            assert current_layout_view is not None
            current_snapshot = document_service.build_reorder_preview_snapshot(
                document_view,
                current_layout_view,
            )
            current_document_view = document_service.build_document_view(
                current_snapshot.text
            )
            current_render_plan = syntax_service.build_render_plan(
                current_document_view,
                cast(Any, syntax_profile),
            )
            base_drag_preview_snapshot = (
                document_service.build_reorder_preview_snapshot(
                    document_view,
                    base_drag_layout_view,
                )
            )
            base_drag_document_view = document_service.build_document_view(
                base_drag_preview_snapshot.text
            )
            base_drag_render_plan = syntax_service.build_render_plan(
                base_drag_document_view,
                cast(Any, syntax_profile),
            )
            editor.set_reorder_preview_state(
                PromptReorderPreviewState(
                    preview_snapshot=PromptReorderProjectionSnapshot(
                        document_view=current_document_view,
                        render_plan=current_render_plan,
                        chip_rendered_ranges_by_index=current_snapshot.chip_rendered_ranges_by_index,
                        chip_owned_ranges_by_index=current_snapshot.chip_owned_ranges_by_index,
                        gap_ranges_by_index=current_snapshot.gap_ranges_by_index,
                    ),
                    base_drag_snapshot=PromptReorderProjectionSnapshot(
                        document_view=base_drag_document_view,
                        render_plan=base_drag_render_plan,
                        chip_rendered_ranges_by_index=base_drag_preview_snapshot.chip_rendered_ranges_by_index,
                        chip_owned_ranges_by_index=base_drag_preview_snapshot.chip_owned_ranges_by_index,
                        gap_ranges_by_index=base_drag_preview_snapshot.gap_ranges_by_index,
                    ),
                    ordered_chip_indices=ordered_chip_indices,
                    dragged_chip_index=None,
                )
            )
            overlay.set_preview_snapshot(
                None,
                base_drag_snapshot=base_drag_preview_snapshot,
                ordered_chip_indices=ordered_chip_indices,
            )
            return
        preview_snapshot = document_service.build_reorder_preview_snapshot(
            document_view,
            preview_layout_view,
        )
        base_drag_snapshot = None
        base_drag_projection_snapshot = None
        if base_drag_layout_view is not None:
            base_drag_snapshot = document_service.build_reorder_preview_snapshot(
                document_view,
                base_drag_layout_view,
            )
            base_drag_document_view = document_service.build_document_view(
                base_drag_snapshot.text
            )
            base_drag_render_plan = syntax_service.build_render_plan(
                base_drag_document_view,
                cast(Any, syntax_profile),
            )
            base_drag_projection_snapshot = PromptReorderProjectionSnapshot(
                document_view=base_drag_document_view,
                render_plan=base_drag_render_plan,
                chip_rendered_ranges_by_index=base_drag_snapshot.chip_rendered_ranges_by_index,
                chip_owned_ranges_by_index=base_drag_snapshot.chip_owned_ranges_by_index,
                gap_ranges_by_index=base_drag_snapshot.gap_ranges_by_index,
            )
        preview_document_view = document_service.build_document_view(
            preview_snapshot.text
        )
        preview_render_plan = syntax_service.build_render_plan(
            preview_document_view,
            cast(Any, syntax_profile),
        )
        editor.set_reorder_preview_state(
            PromptReorderPreviewState(
                preview_snapshot=PromptReorderProjectionSnapshot(
                    document_view=preview_document_view,
                    render_plan=preview_render_plan,
                    chip_rendered_ranges_by_index=preview_snapshot.chip_rendered_ranges_by_index,
                    chip_owned_ranges_by_index=preview_snapshot.chip_owned_ranges_by_index,
                    gap_ranges_by_index=preview_snapshot.gap_ranges_by_index,
                ),
                base_drag_snapshot=base_drag_projection_snapshot,
                ordered_chip_indices=ordered_chip_indices,
                dragged_chip_index=overlay.pointer_reorder_state().dragged_segment_index,
            )
        )
        overlay.set_preview_snapshot(
            preview_snapshot,
            base_drag_snapshot=base_drag_snapshot,
            ordered_chip_indices=ordered_chip_indices,
        )

    overlay.previewLayoutChanged.connect(_sync_preview_state)


def _set_preview_layout(
    editor: PromptEditor,
    overlay: SegmentReorderOverlay,
    *,
    layout_view: object,
) -> None:
    """Force one specific preview layout through the surface-owned preview pipeline."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(_EmptyPromptWildcardCatalogGateway())
    syntax_profile = PromptSyntaxProfileService().default_profile()
    document_view = document_service.build_document_view(editor.toPlainText())
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        cast(Any, layout_view),
    )
    ordered_chip_indices = tuple(
        document_service.reorder_layout_chip_indices(cast(Any, layout_view))
    )
    preview_document_view = document_service.build_document_view(preview_snapshot.text)
    preview_render_plan = syntax_service.build_render_plan(
        preview_document_view,
        syntax_profile,
    )
    editor.set_reorder_preview_state(
        PromptReorderPreviewState(
            preview_snapshot=PromptReorderProjectionSnapshot(
                document_view=preview_document_view,
                render_plan=preview_render_plan,
                chip_rendered_ranges_by_index=preview_snapshot.chip_rendered_ranges_by_index,
                chip_owned_ranges_by_index=preview_snapshot.chip_owned_ranges_by_index,
                gap_ranges_by_index=preview_snapshot.gap_ranges_by_index,
            ),
            base_drag_snapshot=None,
            ordered_chip_indices=ordered_chip_indices,
            dragged_chip_index=None,
        )
    )
    overlay.set_preview_snapshot(
        preview_snapshot,
        base_drag_snapshot=None,
        ordered_chip_indices=ordered_chip_indices,
    )
