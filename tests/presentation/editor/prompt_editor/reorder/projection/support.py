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

"""Provide shared prompt reorder preview-projection fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

import pytest


from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
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
from substitute.presentation.editor.prompt_editor.projection.reorder_preview_projection_contracts import (
    PromptReorderPreviewProjectionContext,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview_projection_owner import (
    PromptReorderPreviewProjectionOwner,
)
from tests.support.prompt_editor.autocomplete_support import (
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


def _service() -> PromptReorderPreviewProjectionOwner:
    """Build one preview projection service for focused ownership tests."""

    return PromptReorderPreviewProjectionOwner(
        projection_applicator=PromptProjectionApplicator(PromptProjectionBuilder()),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )


def _context(
    *,
    source_revision: int = 1,
    viewport_width: int = 480,
    preview_layout_key: tuple[object, ...] | None = ("preview", 1),
    base_drag_layout_key: tuple[object, ...] | None = ("base", 1),
    active_drop_target_identity: tuple[object, ...] | None = ("line", 0, 0),
) -> PromptReorderPreviewProjectionContext:
    """Return one deterministic projection-service cache context."""

    return PromptReorderPreviewProjectionContext(
        source_revision=source_revision,
        layout_width=320.0,
        viewport_width=viewport_width,
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
            preview_layout_key=context.preview_layout_key,
            base_drag_layout_key=context.base_drag_layout_key,
            active_drop_target_identity=context.active_drop_target_identity,
        )
    if field_name == "viewport_width":
        return PromptReorderPreviewProjectionContext(
            source_revision=context.source_revision,
            layout_width=context.layout_width,
            viewport_width=cast(int, field_value),
            preview_layout_key=context.preview_layout_key,
            base_drag_layout_key=context.base_drag_layout_key,
            active_drop_target_identity=context.active_drop_target_identity,
        )
    if field_name == "preview_layout_key":
        return PromptReorderPreviewProjectionContext(
            source_revision=context.source_revision,
            layout_width=context.layout_width,
            viewport_width=context.viewport_width,
            preview_layout_key=cast(tuple[object, ...], field_value),
            base_drag_layout_key=context.base_drag_layout_key,
            active_drop_target_identity=context.active_drop_target_identity,
        )
    if field_name == "base_drag_layout_key":
        return PromptReorderPreviewProjectionContext(
            source_revision=context.source_revision,
            layout_width=context.layout_width,
            viewport_width=context.viewport_width,
            preview_layout_key=context.preview_layout_key,
            base_drag_layout_key=cast(tuple[object, ...], field_value),
            active_drop_target_identity=context.active_drop_target_identity,
        )
    if field_name == "active_drop_target_identity":
        return PromptReorderPreviewProjectionContext(
            source_revision=context.source_revision,
            layout_width=context.layout_width,
            viewport_width=context.viewport_width,
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
