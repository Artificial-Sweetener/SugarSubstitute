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

"""Tests for projection-owned prompt segment reorder preview service state."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from dataclasses import replace
from typing import cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptLineDropTarget,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.projection.applicator import (
    PromptProjectionApplicator,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview import (
    PromptReorderPreviewState,
    PromptReorderProjectionSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview_projection import (
    PromptReorderPreviewProjectionContext,
    PromptReorderPreviewProjectionService,
)
from substitute.presentation.editor.prompt_editor.projection.theme import (
    semantic_palette_from_theme,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)

_LOGGER_NAME = (
    "sugarsubstitute.presentation.editor.prompt_editor.projection.observability"
)


@pytest.fixture()
def app() -> Iterator[QApplication]:
    """Return a Qt application for projection layout construction."""

    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication([])
    yield cast(QApplication, qt_app)


def test_reorder_projection_service_reuses_active_preview_projection(
    app: QApplication,
) -> None:
    """Setting the same preview state twice should reuse active projection layouts."""

    _ = app
    service = _service()
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    context = _context()

    service.set_preview_state(
        preview_state,
        context=context,
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    service.set_preview_state(
        preview_state,
        context=context,
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )

    counters = service.counters()
    assert counters["projection_snapshot_rebuild_count"] == 2
    assert counters["preview_projection_active_cache_hit_count"] == 1


def test_reorder_projection_service_clears_preview_only_state(
    app: QApplication,
) -> None:
    """Clearing preview state should clear active preview and base-drag layouts."""

    _ = app
    service = _service()
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    service.set_preview_state(
        preview_state,
        context=_context(),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    invalidation = service.set_preview_state(
        None,
        context=_context(),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )

    assert invalidation.clear_all_geometry_reason == "reorder_preview_clear"
    assert service.preview_state is None
    assert service.preview_document is None
    assert service.preview_layout is None
    assert service.base_drag_document is None
    assert service.base_drag_layout is None
    assert not service.is_active()


def test_reorder_projection_service_lru_hit_does_not_rebuild_projection(
    app: QApplication,
) -> None:
    """Revisiting a cached preview target should reuse the service LRU entry."""

    _ = app
    service = _service()
    preview_state_a = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_state_b = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    service.set_preview_state(
        preview_state_a,
        context=_context(active_drop_target_identity=("line", 0, 0)),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    service.set_preview_state(
        preview_state_b,
        context=_context(active_drop_target_identity=("line", 0, 2)),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    before_revisit = service.counters()
    service.set_preview_state(
        preview_state_a,
        context=_context(active_drop_target_identity=("line", 0, 0)),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    after_revisit = service.counters()

    assert (
        after_revisit["projection_snapshot_rebuild_count"]
        == before_revisit["projection_snapshot_rebuild_count"]
    )
    assert _counter(after_revisit, "preview_projection_lru_cache_hit_count") == (
        _counter(before_revisit, "preview_projection_lru_cache_hit_count") + 1
    )


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("source_revision", 2),
        ("viewport_width", 481),
        ("scroll_offset", 12),
        ("preview_layout_key", ("layout", "changed")),
        ("base_drag_layout_key", ("base-layout", "changed")),
        ("active_drop_target_identity", ("line", 0, 2)),
    ],
)
def test_reorder_projection_service_cache_key_includes_rebuild_inputs(
    app: QApplication,
    field_name: str,
    field_value: object,
) -> None:
    """Projection cache identity should include source, viewport, layout, and target."""

    _ = app
    service = _service()
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    base_context = _context()

    service.set_preview_state(
        preview_state,
        context=base_context,
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    before_changed_context = service.counters()
    changed_context = _changed_context(base_context, field_name, field_value)
    service.set_preview_state(
        preview_state,
        context=changed_context,
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    after_changed_context = service.counters()

    assert _counter(after_changed_context, "projection_snapshot_rebuild_count") > (
        _counter(before_changed_context, "projection_snapshot_rebuild_count")
    )


def test_reorder_projection_service_cache_key_includes_render_plan(
    app: QApplication,
) -> None:
    """Changing renderer-visible syntax inputs should rebuild preview projection."""

    _ = app
    service = _service()
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    changed_preview_snapshot = replace(
        preview_state.preview_snapshot,
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
    )

    service.set_preview_state(
        preview_state,
        context=_context(),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    before_changed_render_plan = service.counters()
    service.set_preview_state(
        replace(preview_state, preview_snapshot=changed_preview_snapshot),
        context=_context(),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    after_changed_render_plan = service.counters()

    assert _counter(
        after_changed_render_plan,
        "projection_snapshot_rebuild_count",
    ) > _counter(before_changed_render_plan, "projection_snapshot_rebuild_count")


def test_reorder_projection_service_cache_key_includes_font(
    app: QApplication,
) -> None:
    """Changing layout font inputs should rebuild preview and base-drag layouts."""

    _ = app
    service = _service()
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    font = QFont()
    changed_font = QFont(font)
    changed_font.setPointSize(font.pointSize() + 3)

    service.set_preview_state(
        preview_state,
        context=_context(),
        font=font,
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    before_changed_font = service.counters()
    service.set_preview_state(
        preview_state,
        context=_context(),
        font=changed_font,
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    after_changed_font = service.counters()

    assert _counter(after_changed_font, "projection_snapshot_rebuild_count") > (
        _counter(before_changed_font, "projection_snapshot_rebuild_count")
    )


def test_reorder_projection_service_cache_logging_context_is_prompt_safe(
    app: QApplication,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cache diagnostics should log hashes and counts without prompt content."""

    _ = app
    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)
    prompt_text = "secret phrase alpha, beta, gamma"
    service = _service()
    preview_state = _build_reorder_preview_state(
        prompt_text,
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    service.set_preview_state(
        preview_state,
        context=_context(),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    service.set_preview_state(
        preview_state,
        context=_context(active_drop_target_identity=("line", 0, 1)),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "secret phrase" not in messages
    assert "source_text" not in messages
    assert "projection_cache_snapshot_hash" in messages


def _service() -> PromptReorderPreviewProjectionService:
    """Build one preview projection service for focused ownership tests."""

    return PromptReorderPreviewProjectionService(
        projection_applicator=PromptProjectionApplicator(PromptProjectionBuilder()),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )


def _context(
    *,
    source_revision: int = 1,
    viewport_width: int = 480,
    scroll_offset: int = 0,
    preview_layout_key: tuple[object, ...] | None = ("preview", 1),
    base_drag_layout_key: tuple[object, ...] | None = ("base", 1),
    active_drop_target_identity: tuple[object, ...] | None = ("line", 0, 0),
) -> PromptReorderPreviewProjectionContext:
    """Return one deterministic projection-service cache context."""

    return PromptReorderPreviewProjectionContext(
        source_revision=source_revision,
        layout_width=320.0,
        viewport_width=viewport_width,
        scroll_offset=scroll_offset,
        preview_layout_key=preview_layout_key,
        base_drag_layout_key=base_drag_layout_key,
        active_drop_target_identity=active_drop_target_identity,
    )


def _changed_context(
    context: PromptReorderPreviewProjectionContext,
    field_name: str,
    field_value: object,
) -> PromptReorderPreviewProjectionContext:
    """Return one context with a single supported cache-key field changed."""

    if field_name == "source_revision":
        return PromptReorderPreviewProjectionContext(
            source_revision=cast(int, field_value),
            layout_width=context.layout_width,
            viewport_width=context.viewport_width,
            scroll_offset=context.scroll_offset,
            preview_layout_key=context.preview_layout_key,
            base_drag_layout_key=context.base_drag_layout_key,
            active_drop_target_identity=context.active_drop_target_identity,
        )
    if field_name == "viewport_width":
        return PromptReorderPreviewProjectionContext(
            source_revision=context.source_revision,
            layout_width=context.layout_width,
            viewport_width=cast(int, field_value),
            scroll_offset=context.scroll_offset,
            preview_layout_key=context.preview_layout_key,
            base_drag_layout_key=context.base_drag_layout_key,
            active_drop_target_identity=context.active_drop_target_identity,
        )
    if field_name == "scroll_offset":
        return PromptReorderPreviewProjectionContext(
            source_revision=context.source_revision,
            layout_width=context.layout_width,
            viewport_width=context.viewport_width,
            scroll_offset=cast(int, field_value),
            preview_layout_key=context.preview_layout_key,
            base_drag_layout_key=context.base_drag_layout_key,
            active_drop_target_identity=context.active_drop_target_identity,
        )
    if field_name == "preview_layout_key":
        return PromptReorderPreviewProjectionContext(
            source_revision=context.source_revision,
            layout_width=context.layout_width,
            viewport_width=context.viewport_width,
            scroll_offset=context.scroll_offset,
            preview_layout_key=cast(tuple[object, ...], field_value),
            base_drag_layout_key=context.base_drag_layout_key,
            active_drop_target_identity=context.active_drop_target_identity,
        )
    if field_name == "base_drag_layout_key":
        return PromptReorderPreviewProjectionContext(
            source_revision=context.source_revision,
            layout_width=context.layout_width,
            viewport_width=context.viewport_width,
            scroll_offset=context.scroll_offset,
            preview_layout_key=context.preview_layout_key,
            base_drag_layout_key=cast(tuple[object, ...], field_value),
            active_drop_target_identity=context.active_drop_target_identity,
        )
    if field_name == "active_drop_target_identity":
        return PromptReorderPreviewProjectionContext(
            source_revision=context.source_revision,
            layout_width=context.layout_width,
            viewport_width=context.viewport_width,
            scroll_offset=context.scroll_offset,
            preview_layout_key=context.preview_layout_key,
            base_drag_layout_key=context.base_drag_layout_key,
            active_drop_target_identity=cast(tuple[object, ...], field_value),
        )
    raise AssertionError(f"unsupported context field: {field_name}")


def _counter(counters: dict[str, object], name: str) -> int:
    """Return an integer counter from a service counter snapshot."""

    return cast(int, counters[name])


def _build_reorder_preview_state(
    text: str,
    *,
    dragged_chip_index: int,
    drop_target: PromptLineDropTarget,
) -> PromptReorderPreviewState:
    """Build one projection-ready preview state from prompt-editor services."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(EmptyPromptWildcardCatalogGateway())
    syntax_profile = prompt_syntax_profile("emphasis", "wildcard")
    document_view = document_service.build_document_view(text)
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=dragged_chip_index,
        drop_target=drop_target,
    )
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout_view,
    )
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=dragged_chip_index,
    )
    base_drag_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        base_drag_layout_view,
    )
    preview_document_view = document_service.build_document_view(preview_snapshot.text)
    preview_render_plan = syntax_service.build_render_plan(
        preview_document_view,
        syntax_profile,
    )
    base_drag_document_view = document_service.build_document_view(
        base_drag_snapshot.text
    )
    base_drag_render_plan = syntax_service.build_render_plan(
        base_drag_document_view,
        syntax_profile,
    )
    return PromptReorderPreviewState(
        preview_snapshot=PromptReorderProjectionSnapshot(
            document_view=preview_document_view,
            render_plan=preview_render_plan,
            chip_rendered_ranges_by_index=preview_snapshot.chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=preview_snapshot.chip_owned_ranges_by_index,
            gap_ranges_by_index=preview_snapshot.gap_ranges_by_index,
        ),
        base_drag_snapshot=PromptReorderProjectionSnapshot(
            document_view=base_drag_document_view,
            render_plan=base_drag_render_plan,
            chip_rendered_ranges_by_index=base_drag_snapshot.chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=base_drag_snapshot.chip_owned_ranges_by_index,
            gap_ranges_by_index=base_drag_snapshot.gap_ranges_by_index,
        ),
        ordered_chip_indices=tuple(
            document_service.reorder_layout_chip_indices(preview_layout_view)
        ),
        dragged_chip_index=dragged_chip_index,
    )
