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

"""Verify atomic prompt-reorder preview-state construction below interactions."""

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview import (
    reorder_drop_target_identity,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview_state_builder import (
    PromptReorderPreviewBuildRequest,
    PromptReorderPreviewStateBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_projection_snapshot_provider import (
    PromptReorderPreviewProjectionProvider,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)


def test_preview_state_builder_returns_one_atomic_clear_publication() -> None:
    """Missing target and base geometry should produce one complete clear value."""

    document_service, builder = _builder()
    document_view = document_service.build_document_view("alpha, beta")

    publication = builder.build(
        PromptReorderPreviewBuildRequest(
            document_view=document_view,
            preview_layout_view=None,
            base_drag_layout_view=None,
            preview_reorder_state=None,
            base_drag_reorder_state=None,
            ordered_chip_indices=(0, 1),
            dragged_segment_index=None,
            drop_target=None,
            source_revision=3,
            viewport_width=320,
            gesture_id=5,
            event_id=7,
            reason="clear",
        )
    )

    assert publication.preview_state is None
    assert publication.preview_snapshot is None
    assert publication.base_drag_snapshot is None
    assert publication.ordered_chip_indices == (0, 1)


def test_preview_state_builder_publishes_current_and_base_drag_together() -> None:
    """Pre-target drag state should retain current text plus the hidden-chip base."""

    document_service, builder = _builder()
    document_view = document_service.build_document_view("alpha, beta, gamma")
    session = document_service.build_reorder_session_view(document_view)
    base = document_service.build_base_drag_state(
        document_view,
        session.reorder_state,
        current_layout_view=session.layout_view,
        dragged_segment_index=1,
    )

    publication = builder.build(
        PromptReorderPreviewBuildRequest(
            document_view=document_view,
            preview_layout_view=None,
            base_drag_layout_view=base.layout_view,
            preview_reorder_state=None,
            base_drag_reorder_state=base.reorder_state,
            ordered_chip_indices=(0, 1, 2),
            dragged_segment_index=1,
            drop_target=None,
            source_revision=3,
            viewport_width=320,
            gesture_id=5,
            event_id=7,
            reason="drag_start",
        )
    )

    assert publication.preview_state is not None
    assert publication.preview_state.preview_snapshot.document_view.source_text == (
        "alpha, beta, gamma"
    )
    assert publication.preview_state.base_drag_snapshot is not None
    assert publication.preview_state.dragged_chip_index is None
    assert publication.preview_snapshot is None
    assert publication.base_drag_snapshot is not None


def test_preview_state_builder_reuses_equal_active_and_base_projection() -> None:
    """Equal target and base facts should reuse the exact semantic snapshot."""

    document_service, builder = _builder()
    document_view = document_service.build_document_view("alpha, beta, gamma")
    session = document_service.build_reorder_session_view(document_view)
    drop_target = PromptLineDropTarget(row_index=0, insertion_index=0)
    base = document_service.build_base_drag_state(
        document_view,
        session.reorder_state,
        current_layout_view=session.layout_view,
        dragged_segment_index=1,
    )

    publication = builder.build(
        PromptReorderPreviewBuildRequest(
            document_view=document_view,
            preview_layout_view=base.layout_view,
            base_drag_layout_view=base.layout_view,
            preview_reorder_state=base.reorder_state,
            base_drag_reorder_state=base.reorder_state,
            ordered_chip_indices=(0, 1, 2),
            dragged_segment_index=1,
            drop_target=drop_target,
            source_revision=3,
            viewport_width=320,
            gesture_id=5,
            event_id=7,
            reason="drag_move",
        )
    )

    assert publication.preview_state is not None
    assert (
        publication.preview_state.base_drag_snapshot
        is publication.preview_state.preview_snapshot
    )
    assert publication.base_drag_snapshot is publication.preview_snapshot
    assert publication.preview_state.active_drop_target_identity == ("line", 0, 0)


def test_preview_state_builder_excludes_uncommitted_trailing_gap_from_active_frame() -> (
    None
):
    """Active keyboard previews should serialize the same layout as their commit."""

    document_service, builder = _builder()
    document_view = document_service.build_document_view("alpha,\n\nbeta,")
    session = document_service.build_reorder_session_view(document_view)
    base = document_service.build_base_drag_state(
        document_view,
        session.reorder_state,
        current_layout_view=session.layout_view,
        dragged_segment_index=1,
    )
    drop_target = PromptGapBlankLineDropTarget(gap_index=0, blank_line_index=0)
    preview = document_service.build_preview_drop_state(
        document_view,
        base,
        dragged_segment_index=1,
        drop_target=drop_target,
    )

    publication = builder.build(
        PromptReorderPreviewBuildRequest(
            document_view=document_view,
            preview_layout_view=preview.layout_view,
            base_drag_layout_view=base.layout_view,
            preview_reorder_state=preview.reorder_state,
            base_drag_reorder_state=base.reorder_state,
            ordered_chip_indices=preview.reorder_state.ordered_chip_indices,
            dragged_segment_index=1,
            drop_target=drop_target,
            source_revision=3,
            viewport_width=320,
            gesture_id=5,
            event_id=7,
            reason="keyboard_reorder_key",
        )
    )

    expected_text = "alpha,\nbeta,"
    assert publication.preview_state is not None
    assert publication.preview_snapshot is not None
    assert publication.preview_snapshot.text == expected_text
    assert (
        publication.preview_state.preview_snapshot.document_view.source_text
        == expected_text
    )


def test_reorder_drop_target_identity_rejects_unhashable_adapter_values() -> None:
    """Cache identity should preserve typed targets and reject mutable objects."""

    assert reorder_drop_target_identity(
        PromptLineDropTarget(row_index=2, insertion_index=4)
    ) == ("line", 2, 4)
    assert reorder_drop_target_identity(["mutable"]) is None


def _builder() -> tuple[PromptDocumentService, PromptReorderPreviewStateBuilder]:
    """Return matching document, syntax, and projection owners."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(EmptyPromptWildcardCatalogGateway())
    provider = PromptReorderPreviewProjectionProvider(
        document_service=document_service,
        syntax_service=syntax_service,
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
    )
    return document_service, PromptReorderPreviewStateBuilder(
        document_service=document_service,
        projection_provider=provider,
    )
