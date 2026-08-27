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

"""Verify LoRA thumbnail prewarming and media publication."""

from __future__ import annotations


import pytest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.lora.resolution import (
    PromptLoraResolutionStatus,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionThumbnailVariant,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.projection.lora_surface_features import (
    PromptSurfaceLoraFeatureDelegate,
    _is_visible_lora_thumbnail_candidate,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview import (
    PromptReorderPreviewState,
    PromptReorderProjectionSnapshot,
)
from tests.support.prompt_editor.autocomplete_support import (
    prompt_syntax_profile,
)
from tests.support.prompt_editor.projection_surface_support import (
    RecordingThumbnailAssetRepository,
    StaticPromptLoraCatalog,
    install_lora_wildcard_prompt_state,
    lora_catalog_item_with_banner,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    render_surface_viewport,
    set_surface_prompt_state,
)
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
)
from tests.support.prompt_editor.projection_surface_factory import (
    new_projection_surface,
)


def test_projection_surface_reorder_preview_suppresses_lora_banner_reads(
    widgets: list[QWidget],
) -> None:
    """Reorder preview should keep LoRA geometry without extra banner reads."""

    app = ensure_qapp()
    thumbnail_repository = RecordingThumbnailAssetRepository()
    thumbnail_cache = PromptLoraThumbnailCache(thumbnail_repository)
    surface = new_projection_surface(lora_thumbnail_cache=thumbnail_cache)
    widgets.append(surface)
    surface.resize(420, 120)
    surface.show()
    process_events(app)

    document_service = PromptDocumentService()
    syntax_profile = prompt_syntax_profile("lora")
    syntax_service = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        StaticPromptLoraCatalog((lora_catalog_item_with_banner(),)),
    )
    text = "<lora:midna:0.80>, alpha, beta"
    document_view = document_service.build_document_view(text)
    render_plan = syntax_service.build_render_plan(document_view, syntax_profile)
    set_surface_prompt_state(surface, document_view, render_plan)
    normal_range = (
        document_view.lora_spans[0].outer_start,
        document_view.lora_spans[0].outer_end,
    )
    normal_fragments = surface.source_range_fragments(
        start=normal_range[0],
        end=normal_range[1],
    )

    render_surface_viewport(surface)
    process_events(app)

    assert thumbnail_repository.reads == ["midna:banner:768x160"]
    assert normal_fragments
    thumbnail_repository.reads.clear()

    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=2,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout_view,
    )
    preview_document_view = document_service.build_document_view(preview_snapshot.text)
    preview_render_plan = syntax_service.build_render_plan(
        preview_document_view,
        syntax_profile,
    )
    surface.set_reorder_preview_state(
        PromptReorderPreviewState(
            preview_snapshot=PromptReorderProjectionSnapshot(
                document_view=preview_document_view,
                render_plan=preview_render_plan,
                chip_rendered_ranges_by_index=(
                    preview_snapshot.chip_rendered_ranges_by_index
                ),
                chip_owned_ranges_by_index=preview_snapshot.chip_owned_ranges_by_index,
                gap_ranges_by_index=preview_snapshot.gap_ranges_by_index,
            ),
            base_drag_snapshot=None,
            ordered_chip_indices=tuple(
                document_service.reorder_layout_chip_indices(preview_layout_view)
            ),
            dragged_chip_index=2,
        )
    )
    lora_preview_range = preview_snapshot.chip_rendered_ranges_by_index[0]
    preview_fragments = surface.reorder_preview_fragments(
        start=lora_preview_range[0],
        end=lora_preview_range[1],
    )

    render_surface_viewport(surface)

    assert thumbnail_repository.reads == []
    assert preview_fragments
    assert preview_fragments[0].size() == normal_fragments[0].size()


def test_projection_surface_prewarms_lora_banners_after_layout_sync(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Projection rebuild should queue visible LoRA thumbnails after layout is current."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    surface.resize(420, 120)
    original_sync_layout_state = surface._sync_layout_state  # noqa: SLF001
    events: list[str] = []

    def record_sync_layout_state(*, commit_projection: bool = False) -> None:
        """Record layout sync while preserving production behavior."""

        original_sync_layout_state(commit_projection=commit_projection)
        if commit_projection:
            events.append("layout")

    def record_prewarm(
        _delegate: PromptSurfaceLoraFeatureDelegate,
        _geometry: object,
    ) -> int:
        """Record the authoritative visible-banner prewarm call."""

        events.append("prewarm")
        return 0

    monkeypatch.setattr(surface, "_sync_layout_state", record_sync_layout_state)
    monkeypatch.setattr(
        PromptSurfaceLoraFeatureDelegate,
        "prewarm_visible_banners",
        record_prewarm,
    )
    install_lora_wildcard_prompt_state(surface, "<lora:midna:1>")
    surface._rebuild_projection()  # noqa: SLF001

    assert events[-2:] == ["layout", "prewarm"]


def test_lora_thumbnail_publication_advances_only_relevant_content_media(
    widgets: list[QWidget],
) -> None:
    """Unrelated thumbnail completion must not invalidate prompt rendering."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    surface.resize(420, 120)
    install_lora_wildcard_prompt_state(surface, "<lora:midna:1>")
    token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )
    assert token.thumbnail_variants
    storage_key = token.thumbnail_variants[0].storage_key
    owner = surface._content_media_owner  # noqa: SLF001
    render_owner = surface._render_frame_owner  # noqa: SLF001
    initial_identity = owner.identity
    initial_frame = render_owner.frame

    surface._lora_feature_delegate.update_lora_thumbnail_pixmap(  # noqa: SLF001
        surface._layout.frame.geometry,  # noqa: SLF001
        "unrelated:thumbnail",
    )

    assert owner.identity is initial_identity
    assert render_owner.frame is initial_frame

    surface._lora_feature_delegate.update_lora_thumbnail_pixmap(  # noqa: SLF001
        surface._layout.frame.geometry,  # noqa: SLF001
        storage_key,
    )

    assert owner.identity.revision == initial_identity.revision + 1
    assert render_owner.frame is not initial_frame
    assert render_owner.frame.content_media_identity is owner.identity


def test_projection_surface_prewarms_pending_lora_tokens_with_thumbnails() -> None:
    """Thumbnail-bearing LoRA chips should not wait for authoritative catalog status."""

    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=20,
        display_text="Midna",
        value_text="1",
        lora_status=PromptLoraResolutionStatus.PENDING_NO_AUTHORITY,
        thumbnail_variants=(
            PromptProjectionThumbnailVariant(
                size=768,
                storage_key="midna:banner:768x160",
                width=768,
                height=160,
                content_format="png",
                byte_size=1024,
                role=BANNER_THUMBNAIL_ROLE,
            ),
        ),
    )

    assert _is_visible_lora_thumbnail_candidate(token) is True
