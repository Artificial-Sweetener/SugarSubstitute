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

"""Tests for prompt projection LoRA surface behavior."""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, cast
from uuid import UUID

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QPointF
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptLineDropTarget,
    PromptDocumentService,
    PromptLoraRendererView,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.application.prompt_editor.prompt_lora_resolution_service import (
    PromptLoraResolutionStatus,
)
from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
    ModelMetadataMenuItem,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionThumbnailVariant,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview import (
    PromptReorderPreviewState,
    PromptReorderProjectionSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.lora_surface_features import (
    _is_visible_lora_thumbnail_candidate,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    prompt_syntax_profile,
)
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory
from tests.prompt_projection_surface_test_helpers import (
    apply_source_range_to_projection,
    delay_projection_update_scheduler,
    flush_projection_update_scheduler,
    install_lora_wildcard_prompt_state,
    lora_catalog_item_with_banner,
    PositionEvent,
    new_projection_surface,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    RecordingThumbnailAssetRepository,
    render_surface_viewport,
    StaticPromptLoraCatalog,
    surface_router,
    valid_transient_insertion_overlay,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _MetadataActionHandler:
    """Record prompt-editor LoRA metadata action targets."""

    def __init__(self) -> None:
        """Prepare refresh observations."""

        self.refresh_targets: list[object] = []

    def refresh_civitai_metadata(self, target: object) -> None:
        """Record one metadata refresh target."""

        self.refresh_targets.append(target)

    def output_canvas_thumbnail_choices(
        self,
    ) -> tuple[OutputCanvasThumbnailChoice, ...]:
        """Return no output choices for existing surface tests."""

        return ()

    def active_output_canvas_thumbnail_choice(
        self,
    ) -> OutputCanvasThumbnailChoice | None:
        """Return no active output choice for existing surface tests."""

        return None

    def set_thumbnail_from_output_image(
        self,
        target: ModelMetadataContextMenuTarget,
        image_id: UUID,
    ) -> None:
        """Ignore output thumbnail requests in existing surface tests."""

        _ = (target, image_id)


def test_projection_surface_requests_lora_context_menu_for_token_with_url(
    widgets: list[QWidget],
) -> None:
    """Inline LoRA right-clicks should request a host-owned context menu."""

    ensure_qapp()
    model_page_url = "https://civitai.com/models/100?modelVersionId=200"
    surface = new_projection_surface()
    widgets.append(surface)
    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=37,
        display_text="Mineru",
        model_page_url=model_page_url,
    )
    emitted: list[tuple[object, QPoint]] = []
    surface.loraContextMenuRequested.connect(
        lambda emitted_token, global_pos: emitted.append((emitted_token, global_pos))
    )
    cast(Any, surface)._token_at_viewport_position = lambda _pos: token

    handled = surface._request_lora_context_menu(  # noqa: SLF001
        QPointF(4.0, 6.0),
        QPoint(40, 60),
    )

    assert handled is True
    assert emitted == [(token, QPoint(40, 60))]


def test_projection_surface_lora_context_menu_requires_url(
    widgets: list[QWidget],
) -> None:
    """Inline LoRA context requests should be skipped when no page URL exists."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=37,
        display_text="Mineru",
        model_page_url=None,
    )
    emitted: list[tuple[object, QPoint]] = []
    surface.loraContextMenuRequested.connect(
        lambda emitted_token, global_pos: emitted.append((emitted_token, global_pos))
    )
    cast(Any, surface)._token_at_viewport_position = lambda _pos: token

    handled = surface._request_lora_context_menu(  # noqa: SLF001
        QPointF(4.0, 6.0),
        QPoint(40, 60),
    )

    assert handled is False
    assert emitted == []


def test_projection_surface_lora_tooltip_uses_full_page_and_version_text(
    widgets: list[QWidget],
) -> None:
    """Inline LoRA hover tooltips should expose unelided page and version labels."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=37,
        display_text="Extremely Long CivitAI Collection Page Name",
        lora_version_text="Overly Detailed Version Name",
    )
    cast(Any, surface)._token_at_viewport_position = lambda _pos: token

    tooltip = surface._lora_tooltip_for_hover_event(  # noqa: SLF001
        surface.viewport(),
        PositionEvent(QPointF(4.0, 6.0)),
    )

    assert tooltip == (
        "Model: Extremely Long CivitAI Collection Page Name\n"
        "Version: Overly Detailed Version Name"
    )


def test_projection_surface_lora_tooltip_reports_missing_lora(
    widgets: list[QWidget],
) -> None:
    """Inline LoRA hover tooltips should report missing catalog entries."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=28,
        display_text="Missing",
        detail_text=r"Unknown\Missing",
        exists=False,
    )
    cast(Any, surface)._token_at_viewport_position = lambda _pos: token

    tooltip = surface._lora_tooltip_for_hover_event(  # noqa: SLF001
        surface.viewport(),
        PositionEvent(QPointF(4.0, 6.0)),
    )

    assert tooltip == r"LoRA not found: Unknown\Missing"


def test_projection_surface_lora_tooltip_ignores_non_lora_tokens(
    widgets: list[QWidget],
) -> None:
    """LoRA label tooltips should not appear for other projected token kinds."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    token = PromptProjectionToken(
        token_id="emphasis:0",
        kind=PromptProjectionTokenKind.EMPHASIS,
        source_start=0,
        source_end=8,
        display_text="cat",
    )
    cast(Any, surface)._token_at_viewport_position = lambda _pos: token

    tooltip = surface._lora_tooltip_for_hover_event(  # noqa: SLF001
        surface.viewport(),
        PositionEvent(QPointF(4.0, 6.0)),
    )

    assert tooltip is None


def test_projection_surface_rebuilds_when_lora_renderer_span_completes_plain_suffix(
    widgets: list[QWidget],
) -> None:
    """LoRA renderer spans should force token projection even without top-level spans."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(420, 180)
    widgets.append(surface)
    surface_router(surface).set_plain_text("<lora:midna:1")
    document_view = PromptDocumentService().build_document_view("<lora:midna:1>")
    full_render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(
            (lora_catalog_item_with_banner(),)
        ),
    ).build_render_plan(document_view, prompt_syntax_profile("lora"))
    lora_renderer_view = cast(
        PromptLoraRendererView,
        full_render_plan.renderer_view_for_kind("lora"),
    )
    renderer_only_render_plan = PromptSyntaxRenderPlan(
        syntax_spans=(),
        renderer_views=(replace(lora_renderer_view, syntax_spans=()),),
    )

    surface.set_prompt_state(document_view, renderer_only_render_plan)

    projection_document = surface.projection_document()
    assert [
        (token.kind, token.source_start, token.source_end)
        for token in projection_document.tokens
    ] == [(PromptProjectionTokenKind.LORA, 0, len("<lora:midna:1>"))]
    assert [
        (run.kind.name, run.renderer_key)
        for run in projection_document.runs
        if run.token_id is not None
    ] == [("INLINE_OBJECT", "lora_chip")]
    assert cast(Any, surface)._layout.inline_object_fragment_count() == 1


def test_projection_surface_lora_chip_stays_within_text_row_height(
    widgets: list[QWidget],
) -> None:
    """LoRA chips should sit inside the canonical row without filling it."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(520, 180)
    widgets.append(surface)
    install_lora_wildcard_prompt_state(surface, "<lora:midna:1> tail")

    layout = cast(Any, surface)._layout
    line = next(
        line
        for line in layout._snapshot.lines  # noqa: SLF001
        if any(
            fragment.__class__.__name__ == "PromptProjectionInlineObjectFragment"
            for fragment in line.fragments
        )
    )
    lora_fragment = next(
        fragment
        for fragment in line.fragments
        if fragment.__class__.__name__ == "PromptProjectionInlineObjectFragment"
    )

    assert line.height == layout.metrics.text_line_height
    assert lora_fragment.rect.height() < layout.metrics.text_line_height


def test_projection_surface_lora_boundary_insert_keeps_inserted_text_plain(
    widgets: list[QWidget],
) -> None:
    """Typing at a LoRA edge should not extend the chip over the new character."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(520, 180)
    widgets.append(surface)
    text = "<lora:midna:1>, tail"
    install_lora_wildcard_prompt_state(surface, text)
    lora_token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )
    insertion_position = lora_token.source_end
    next_text = text[:insertion_position] + "<" + text[insertion_position:]

    apply_source_range_to_projection(
        surface,
        next_text,
        cursor_position=insertion_position + 1,
        anchor_position=insertion_position + 1,
        emit_text_changed=True,
        rebuild_immediately=True,
        optimistic_prompt_state=None,
        source_edit_start=insertion_position,
        source_edit_end=insertion_position,
        source_edit_replacement_text="<",
        previous_source_text=text,
    )

    shifted_lora_token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )
    assert shifted_lora_token.source_start == lora_token.source_start
    assert shifted_lora_token.source_end == lora_token.source_end
    assert surface.cursor_position == insertion_position + 1
    assert surface._cursor_state.token_id is None  # noqa: SLF001
    assert [
        (run.kind.name, run.display_text, run.token_id)
        for run in surface.projection_document().runs
    ] == [
        ("INLINE_OBJECT", "Midna", shifted_lora_token.token_id),
        ("TEXT", "<, tail", None),
    ]


def test_projection_surface_lora_suffix_prefix_defers_without_rebuild(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typing a LoRA prefix after a trailing LoRA chip should keep the key path cheap."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(520, 180)
    widgets.append(surface)
    text = "<lora:midna:1>"
    install_lora_wildcard_prompt_state(surface, text)
    surface.set_defer_source_rebuilds_until_prompt_state(True)
    lora_token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )
    surface.set_cursor_positions(
        cursor_position=lora_token.source_end,
        anchor_position=lora_token.source_end,
    )
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record full projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)

    cast(Any, surface)._insert_viewport_text("<")

    overlay = valid_transient_insertion_overlay(surface)
    assert surface.toPlainText() == f"{text}<"
    assert surface.projection_document().source_text == text
    assert surface.cursor_position == len(text) + 1
    assert overlay is not None
    assert overlay.text == "<"
    assert rebuild_count == 0


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
    surface.set_prompt_state(document_view, render_plan)
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

    def record_prewarm() -> int:
        """Record visible banner prewarm timing."""

        events.append("prewarm")
        return 0

    monkeypatch.setattr(surface, "_sync_layout_state", record_sync_layout_state)
    monkeypatch.setattr(surface, "_prewarm_visible_lora_banners", record_prewarm)
    install_lora_wildcard_prompt_state(surface, "<lora:midna:1>")
    surface._rebuild_projection()  # noqa: SLF001

    assert events[-2:] == ["layout", "prewarm"]


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


def test_projection_surface_schedules_metadata_only_prompt_state(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unchanged-source metadata refreshes should use the projection scheduler."""

    ensure_qapp()
    text = "<lora:midna:1>"
    surface = new_projection_surface()
    surface.resize(240, 180)
    widgets.append(surface)
    surface_router(surface).set_source_text(text)
    document_view = PromptDocumentService().build_document_view(text)
    syntax_profile = prompt_syntax_profile("lora")
    initial_render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(()),
    ).build_render_plan(document_view, syntax_profile)
    metadata_render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(
            (lora_catalog_item_with_banner(),)
        ),
    ).build_render_plan(document_view, syntax_profile)
    surface.set_prompt_state(document_view, initial_render_plan)
    surface.flush_pending_projection_update(reason="test_initial_metadata_state")
    surface.set_cursor_positions(
        cursor_position=len(text),
        anchor_position=len(text),
    )
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    surface.set_prompt_state(document_view, metadata_render_plan)

    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is True

    assert not surface.cursorRect().isNull()
    assert rebuild_count == 1
    assert surface.has_pending_projection_update() is False

    token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )
    assert rebuild_count == 1
    assert surface.has_pending_projection_update() is False
    assert token.thumbnail_variants


def test_projection_surface_scheduled_metadata_failure_remains_retryable(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed scheduled metadata applies should not mark the failed plan current."""

    ensure_qapp()
    text = "<lora:midna:1>, tail"
    surface = new_projection_surface()
    surface.resize(240, 180)
    widgets.append(surface)
    surface_router(surface).set_source_text(text)
    document_view = PromptDocumentService().build_document_view(text)
    syntax_profile = prompt_syntax_profile("lora")
    original_render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(()),
    ).build_render_plan(document_view, syntax_profile)
    metadata_render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(
            (lora_catalog_item_with_banner(),)
        ),
    ).build_render_plan(document_view, syntax_profile)
    surface.set_prompt_state(document_view, original_render_plan)
    surface.flush_pending_projection_update(reason="test_initial_metadata_state")
    surface.set_cursor_positions(
        cursor_position=len(text),
        anchor_position=len(text),
    )
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_attempts = 0

    def fail_rebuild() -> None:
        """Fail the first scheduled metadata projection apply."""

        nonlocal rebuild_attempts
        rebuild_attempts += 1
        raise RuntimeError("projection rebuild failed")

    monkeypatch.setattr(surface, "_rebuild_projection", fail_rebuild)
    monkeypatch.setattr(
        cast(Any, surface)._incremental_apply_controller,
        "can_apply_fast_trailing_insert_for_prompt_state",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        cast(Any, surface)._incremental_apply_controller,
        "try_apply_scheduled_incremental_prompt_state_projection",
        lambda **_kwargs: False,
    )

    surface._projection_freshness_controller.schedule_metadata_update(  # noqa: SLF001
        document_view=document_view,
        render_plan=metadata_render_plan,
        source_revision=surface._source_revision,  # noqa: SLF001
    )

    assert surface.has_pending_projection_update() is True

    flush_projection_update_scheduler(surface)

    assert rebuild_attempts == 1
    assert surface._render_plan == original_render_plan  # noqa: SLF001
    assert surface.has_pending_projection_update() is False

    monkeypatch.setattr(surface, "_rebuild_projection", original_rebuild_projection)
    monkeypatch.undo()
    surface.set_prompt_state(document_view, metadata_render_plan)

    flush_projection_update_scheduler(surface)

    assert surface._render_plan == metadata_render_plan  # noqa: SLF001
    assert surface.has_pending_projection_update() is False


def test_prompt_editor_lora_civitai_action_opens_token_url(
    widgets: list[QWidget],
) -> None:
    """The host-owned inline LoRA action should open the token's CivitAI URL."""

    ensure_qapp()
    opened_urls: list[str] = []
    model_page_url = "https://civitai.com/models/100?modelVersionId=200"

    def open_url(url: str) -> bool:
        """Record opened URLs without launching a browser."""

        opened_urls.append(url)
        return True

    editor = PromptEditor(
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
        prompt_syntax_profile=prompt_syntax_profile("lora"),
        open_url=open_url,
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    widgets.append(editor)
    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=37,
        display_text="Mineru",
        model_page_url=model_page_url,
    )

    presenter = cast(Any, editor)._inline_lora_menu_presenter
    action = presenter.page_action_for_token_context(presenter.token_context(token))

    assert action is not None
    assert action.label == "Go to CivitAI page"
    action.callback()
    assert opened_urls == [model_page_url]


def test_prompt_editor_lora_banner_menu_includes_refresh_action(
    widgets: list[QWidget],
) -> None:
    """The real prompt editor should inject refresh handling into LoRA banners."""

    ensure_qapp()
    handler = _MetadataActionHandler()
    model_page_url = "https://civitai.com/models/100?modelVersionId=200"
    editor = PromptEditor(
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
        prompt_syntax_profile=prompt_syntax_profile("lora"),
        model_metadata_action_handler=handler,
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    widgets.append(editor)
    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=37,
        display_text="Mineru",
        detail_text="mineru",
        lora_backend_value="loras/mineru.safetensors",
        model_page_url=model_page_url,
    )

    presenter = cast(Any, editor)._inline_lora_menu_presenter
    menu_items = presenter.metadata_actions_for_token_context(
        presenter.token_context(token)
    )
    actions = _metadata_menu_actions(menu_items)

    assert [action.label for action in actions] == [
        "Go to CivitAI page",
        "Refresh CivitAI metadata",
        "Set thumbnail from canvas",
    ]
    actions[1].callback()
    assert len(handler.refresh_targets) == 1
    refresh_target = handler.refresh_targets[0]
    assert getattr(refresh_target, "model_kind") == "loras"
    assert getattr(refresh_target, "backend_value") == "loras/mineru.safetensors"


def _metadata_menu_actions(
    items: tuple[ModelMetadataMenuItem, ...],
) -> tuple[ModelMetadataMenuAction, ...]:
    """Return action items from one metadata menu item tuple."""

    return tuple(item for item in items if isinstance(item, ModelMetadataMenuAction))
