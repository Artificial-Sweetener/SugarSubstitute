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

"""Mount real prompt editors and reorder overlays for focused proof."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast


import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfileService,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    SegmentReorderOverlay,
)
from substitute.presentation.editor.prompt_editor.composition.reorder_overlay_factory import (
    PromptSegmentReorderOverlayFactory,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from tests.support.prompt_editor.projection_engine_support import surface_for
from tests.support.execution.runtime_support import (
    immediate_prompt_task_executor_factory,
)
from tests.support.prompt_editor.reorder_pointer_support import (
    PromptReorderPointerTarget,
    drag_prompt_reorder_target_to_global,
    prompt_reorder_pointer_target,
    prompt_reorder_pointer_targets,
)
from tests.support.qt.semantic_wait import wait_for_queued_qt_turn

from .gateway_support import (
    _EmptyPromptAutocompleteGateway,
    _EmptyPromptWildcardCatalogGateway,
)
from .preview_support import _connect_preview_sync


def ensure_qapp() -> QApplication:
    """Return a running Qt application for reorder overlay tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication, cycles: int = 5) -> None:
    """Deliver callbacks queued by an explicitly controlled test action."""

    _ = (app, cycles)
    wait_for_queued_qt_turn()


def _create_editor(
    widgets: list[QWidget],
    *,
    width: int,
    height: int,
    text: str,
) -> PromptEditor:
    """Create one prompt editor inside a visible host widget."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(width, height)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    editor = PromptEditor(
        host,
        prompt_autocomplete_gateway=_EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=PromptSyntaxProfileService().default_profile(),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    layout.addWidget(editor)
    editor.setPlainText(text)
    host.show()
    editor.show()
    widgets.extend([host, editor])
    process_events(app)
    return editor


def _create_overlay(
    widgets: list[QWidget],
    *,
    width: int,
    height: int,
    text: str,
    active_segment_index: int | None = None,
) -> tuple[PromptEditor, SegmentReorderOverlay]:
    """Create one visible overlay bound to a real projection-engine prompt editor."""

    app = ensure_qapp()
    editor = _create_editor(widgets, width=width, height=height, text=text)
    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(_EmptyPromptWildcardCatalogGateway())
    syntax_profile = PromptSyntaxProfileService().default_profile()
    document_view = document_service.build_document_view(text)
    reorder_session = document_service.build_reorder_session_view(document_view)
    overlay_assembly = PromptSegmentReorderOverlayFactory(
        document_service=document_service,
        syntax_service=syntax_service,
        syntax_profile=syntax_profile,
        geometry_owner=surface_for(editor).reorder_geometry_owner,
        interaction_metrics=PromptReorderInteractionMetricsOwner(),
    ).create_segment_overlay(editor, layout_policy=document_service)
    overlay = cast(SegmentReorderOverlay, overlay_assembly.overlay)
    _connect_preview_sync(
        editor,
        overlay,
        document_service=document_service,
        syntax_service=syntax_service,
        syntax_profile=syntax_profile,
        document_view=document_view,
    )
    overlay.set_chips(
        document_view,
        reorder_session.layout_view,
        reorder_session.reorder_state,
        chips=reorder_session.chips,
        active_chip_index=active_segment_index,
    )
    overlay.show()
    overlay.refresh_geometry()
    widgets.append(overlay)
    process_events(app)
    overlay.refresh_geometry()
    process_events(app)
    return editor, overlay


def _pointer_regions(overlay: QWidget) -> list[PromptReorderPointerTarget]:
    """Return visible pointer regions sorted by rendered position."""

    return prompt_reorder_pointer_targets(overlay)


def _chip_by_segment_index(
    overlay: QWidget, segment_index: int
) -> PromptReorderPointerTarget:
    """Return one rendered pointer region by its segment index."""

    return prompt_reorder_pointer_target(overlay, segment_index)


def _chip_text(chip: PromptReorderPointerTarget) -> str:
    """Return the segment label recorded on one reorder pointer region."""

    segment_text = chip.property("segmentText")
    assert isinstance(segment_text, str)
    return segment_text


def _chip_segment_index(chip: PromptReorderPointerTarget) -> int:
    """Return the integer segment index owned by one pointer region."""

    segment_index = chip.property("segmentIndex")
    assert isinstance(segment_index, int)
    return segment_index


def _drag_proxy(overlay: QWidget) -> QWidget:
    """Return the floating drag proxy widget used during segment dragging."""

    return cast(SegmentReorderOverlay, overlay).drag_proxy_widget()


def _drag_proxy_projection_document(
    overlay: QWidget,
) -> PromptProjectionDocument | None:
    """Return the projection document currently rendered by the drag proxy."""

    return cast(
        PromptProjectionDocument | None,
        cast(Any, _drag_proxy(overlay)).projection_document(),
    )


def _drag_proxy_text_paint_payload(overlay: QWidget) -> object | None:
    """Return the prepared projection text payload used by the drag proxy."""

    return cast(object | None, cast(Any, _drag_proxy(overlay)).text_paint_payload())


def _preview_projection_document(
    overlay: QWidget,
) -> PromptProjectionDocument | None:
    """Return the surface-owned projection document currently painted in preview mode."""

    editor = cast(PromptEditor, cast(Any, overlay)._editor)
    return cast(
        PromptProjectionDocument | None,
        getattr(surface_for(editor), "_reorder_preview_projection").preview_document,
    )


def _preview_text(overlay: QWidget) -> str:
    """Return the surface-owned prompt text currently rendered in preview mode."""

    preview_projection_document = _preview_projection_document(overlay)
    if preview_projection_document is None:
        return ""
    return preview_projection_document.source_text


def _preview_rect(overlay: QWidget, segment_index: int) -> QRect | None:
    """Return one preview rect through the overlay port."""

    return cast(SegmentReorderOverlay, overlay).preview_rect_for_segment(segment_index)


def _drag_chip_to_global(
    chip: PromptReorderPointerTarget,
    *,
    global_target: QPoint,
) -> None:
    """Drag one reorder hotspot to the supplied global target point."""

    drag_prompt_reorder_target_to_global(chip, global_target=global_target)


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track and dispose widgets created during one overlay test."""

    created: list[QWidget] = []
    yield created
    app = ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    process_events(app)
