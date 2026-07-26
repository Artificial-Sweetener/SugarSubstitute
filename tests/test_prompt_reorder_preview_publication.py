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

"""Verify focused reorder-preview publication lifecycle ownership."""

from __future__ import annotations

import pytest

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_preview_publication import (
    PromptReorderPreviewPublicationOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_projection_snapshot_provider import (
    PromptReorderPreviewProjectionProvider,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.prompt_reorder_interaction_test_helpers import (
    ControllerEditorDouble,
    MenuCursorDouble,
    OverlayDouble,
    PreviewSyncContextDouble,
)


def test_publication_owner_clears_unbound_preview_without_overlay_work() -> None:
    """An unbound scheduler flush clears only editor preview state."""

    owner, editor, _document_service = _owner_for_text("alpha, beta")

    owner.schedule(reason="no_overlay")
    owner.flush()

    assert editor.clear_reorder_preview_state_calls == 1
    assert owner.state.pending_revision is None
    assert owner.has_bound_session is False


def test_publication_owner_flushes_geometry_then_publishes_one_frame() -> None:
    """A bound owner atomically publishes after coalesced geometry invalidation."""

    owner, editor, document_service = _owner_for_text("alpha, beta")
    document = document_service.build_document_view("alpha, beta")
    layout = document_service.build_reorder_layout_view(document)
    overlay = OverlayDouble([0, 1], current_layout_view=layout)
    overlay._preview_layout_view = layout
    metrics = PromptReorderInteractionMetricsOwner()
    owner.bind_session(
        overlay=overlay,
        build_facts=overlay,
        sync_context=PreviewSyncContextDouble(overlay, metrics),
    )

    owner.schedule(reason="bound_preview")
    owner.flush()

    assert overlay.autoscroll_flush_calls == ["autoscroll_coalesced_preview_sync"]
    assert overlay.preview_fact_snapshot_calls == 1
    assert len(editor.reorder_preview_state_calls) == 1
    assert len(overlay.preview_snapshot_calls) == 1
    assert owner.publishing is False


def test_publication_owner_releases_session_authorities_after_close() -> None:
    """Closing a session drops transient overlay authorities and preview paint."""

    owner, editor, _document_service = _owner_for_text("alpha, beta")
    overlay = OverlayDouble([0, 1])
    owner.bind_session(
        overlay=overlay,
        build_facts=overlay,
        sync_context=PreviewSyncContextDouble(
            overlay,
            PromptReorderInteractionMetricsOwner(),
        ),
    )

    owner.close(reason="overlay_close")
    owner.clear_published_state()
    owner.unbind_session()

    assert editor.clear_reorder_preview_state_calls == 1
    assert owner.has_bound_session is False


def test_publication_owner_releases_atomic_guard_when_overlay_publish_fails() -> None:
    """A publication error cannot strand later session positioning behind a guard."""

    class _FailingOverlay(OverlayDouble):
        """Raise at the overlay half of an otherwise atomic preview publication."""

        def set_preview_snapshot(
            self,
            snapshot: object | None,
            *,
            base_drag_snapshot: object | None = None,
            ordered_chip_indices: tuple[int, ...],
        ) -> None:
            """Fail after the editor has received the prepared preview frame."""

            raise RuntimeError("preview publication failed")

    owner, _editor, document_service = _owner_for_text("alpha, beta")
    document = document_service.build_document_view("alpha, beta")
    layout = document_service.build_reorder_layout_view(document)
    overlay = _FailingOverlay([0, 1], current_layout_view=layout)
    overlay._preview_layout_view = layout
    owner.bind_session(
        overlay=overlay,
        build_facts=overlay,
        sync_context=PreviewSyncContextDouble(
            overlay,
            PromptReorderInteractionMetricsOwner(),
        ),
    )

    owner.schedule(reason="failing_publication")

    with pytest.raises(RuntimeError, match="preview publication failed"):
        owner.flush()

    assert owner.publishing is False


def _owner_for_text(
    text: str,
) -> tuple[
    PromptReorderPreviewPublicationOwner,
    ControllerEditorDouble,
    PromptDocumentService,
]:
    """Build the owner with production projection collaborators and test ports."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(EmptyPromptWildcardCatalogGateway())
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text=text, position=0),
        current_cursor=MenuCursorDouble(text=text, position=0),
        text=text,
    )
    owner = PromptReorderPreviewPublicationOwner(
        clear_preview_state=editor.clear_reorder_preview_state,
        current_document_view=lambda: document_service.build_document_view(text),
        publish_preview_state=editor.set_reorder_preview_state,
        source_identity=editor.prompt_command_source_identity,
        viewport_width=lambda: 0,
        document_service=document_service,
        projection_provider=PromptReorderPreviewProjectionProvider(
            document_service=document_service,
            syntax_service=syntax_service,
            syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        ),
        metrics=PromptReorderInteractionMetricsOwner(),
        interval_ms=PromptReorderPreviewPublicationOwner.DEFAULT_INTERVAL_MS,
    )
    return owner, editor, document_service
