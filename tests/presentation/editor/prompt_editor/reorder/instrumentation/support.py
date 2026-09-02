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

"""Provide shared real-editor support for reorder instrumentation contracts."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest


from PySide6.QtCore import QRectF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptReorderView,
    SegmentReorderOverlay,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview import (
    PromptReorderPreviewState,
    PromptReorderProjectionSnapshot,
)
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.support.execution.runtime_support import (
    immediate_prompt_task_executor_factory,
)

from tests.support.prompt_editor.projection_engine_support import surface_for
from tests.support.prompt_editor.reorder_pointer_support import (
    PromptReorderPointerTarget,
    prompt_reorder_pointer_target,
)
from tests.support.qt.semantic_wait import wait_for_queued_qt_turn

_REDUCED_MOTION_PROPERTY = "substitute.reduce_motion"


class _EmptyPromptAutocompleteGateway:
    """Return deterministic empty autocomplete rows for reorder tests."""

    @staticmethod
    def search(
        _prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no autocomplete suggestions."""

        _ = limit
        return ()


class _EmptyPromptWildcardCatalogGateway:
    """Return deterministic missing wildcard rows for reorder tests."""

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no wildcard autocomplete suggestions."""

        _ = (prefix, limit)
        return ()

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return missing wildcard resolution rows."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=False,
            )
            for reference in references
        )


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track and dispose widgets created during one reorder performance test."""

    created: list[QWidget] = []
    app = _ensure_qapp()
    previous_override = app.property(_REDUCED_MOTION_PROPERTY)
    app.setProperty(_REDUCED_MOTION_PROPERTY, False)
    try:
        yield created
    finally:
        for widget in reversed(created):
            widget.close()
            widget.deleteLater()
        app.setProperty(_REDUCED_MOTION_PROPERTY, previous_override)
        _process_events(app)


def _ensure_qapp() -> QApplication:
    """Return a running Qt application for reorder performance tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _process_events(app: QApplication) -> None:
    """Deliver callbacks queued by an explicitly controlled test action."""

    wait_for_queued_qt_turn()


def _flush_preview_sync(editor: PromptEditor) -> None:
    """Run the pending coalesced reorder timer deterministically."""

    publication_owner = cast(
        Any,
        editor,
    )._interaction_controller._reorder._overlay_session._preview_publication
    if publication_owner.has_pending():
        for _ in range(2):
            publication_owner._scheduler._timer._run()
            if not publication_owner.has_pending():
                break
    assert publication_owner.has_pending() is False


def _create_prompt_editor(
    widgets: list[QWidget],
    *,
    text: str,
    width: int = 420,
    height: int = 220,
) -> PromptEditor:
    """Create one real prompt editor with empty prompt feature gateways."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(width, height)
    layout = QVBoxLayout(host)
    box = PromptEditor(
        host,
        prompt_autocomplete_gateway=_EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    layout.addWidget(box)
    box.setPlainText(text)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    _process_events(app)
    return box


def _overlay_chip_by_segment_index(
    overlay: QWidget, segment_index: int
) -> PromptReorderPointerTarget:
    """Return one production logical pointer target by segment index."""

    return prompt_reorder_pointer_target(overlay, segment_index)


def _editor_reorder_preview_document(
    box: PromptEditor,
) -> PromptProjectionDocument | None:
    """Return the surface-owned reorder preview projection document."""

    return cast(
        PromptProjectionDocument | None,
        getattr(surface_for(box), "_reorder_preview_projection").preview_document,
    )


def _editor_reorder_preview_text(box: PromptEditor) -> str:
    """Return the active reorder preview text without reading source state."""

    preview_document = _editor_reorder_preview_document(box)
    if preview_document is None:
        return ""
    return preview_document.source_text


def _performance_counters(overlay: SegmentReorderOverlay) -> dict[str, object]:
    """Return the current overlay performance counter snapshot."""

    return overlay.reorder_performance_counters()


def _painted_preview_rect(
    overlay: SegmentReorderOverlay,
    segment_index: int,
) -> QRectF:
    """Return the passive view's current painted preview rect for one chip."""

    view = overlay.findChild(PromptReorderView, "segmentReorderView")
    assert view is not None
    for chip in view.render_state.preview_chips:
        if chip.segment_index != segment_index:
            continue
        if chip.geometry is not None:
            return QRectF(chip.geometry.hotspot_rect)
        assert chip.visual is not None
        return QRectF(chip.visual.hotspot_rect)
    raise AssertionError(f"Missing painted preview chip for segment {segment_index}.")


def _open_reorder_overlay(box: PromptEditor) -> SegmentReorderOverlay:
    """Enter reorder mode and return the real editor-owned overlay."""

    app = _ensure_qapp()
    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    return cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))


def _assert_plain_alt_keeps_surface_text_ownership(
    overlay: SegmentReorderOverlay,
) -> None:
    """Assert plain Alt paints chrome while leaving text on the surface."""

    view = overlay.findChild(PromptReorderView, "segmentReorderView")
    assert view is not None
    state = view.render_state
    assert state.preview_active is False
    assert state.live_chips == ()
    assert state.raster_paint_count == 0
    surface_chrome = cast(
        Any, overlay
    )._editor._surface._reorder_surface_visual_state.state.chrome_snapshot
    assert surface_chrome is not None
    assert surface_chrome.mode == "live"
    assert surface_chrome.chips
    assert cast(Any, overlay)._live_visual_owner.visual_snapshots_by_index == {}


def _counter_delta(
    before: dict[str, object],
    after: dict[str, object],
    counter_name: str,
) -> int:
    """Return a typed integer counter delta from two counter snapshots."""

    return cast(int, after[counter_name]) - cast(int, before[counter_name])


def _assert_timing_observed(
    counters: dict[str, object],
    counter_name: str,
) -> None:
    """Assert one GUI timing counter captured a real elapsed observation."""

    value = counters[counter_name]
    assert isinstance(value, float)
    assert value > 0.0


def _build_reorder_preview_state(
    text: str,
    *,
    dragged_chip_index: int,
    drop_target: PromptLineDropTarget,
) -> PromptReorderPreviewState:
    """Build one reorder preview state without importing skipped Qt contract tests."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(_EmptyPromptWildcardCatalogGateway())
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
        base_drag_snapshot.text,
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
            document_service.reorder_layout_chip_indices(preview_layout_view),
        ),
        dragged_chip_index=dragged_chip_index,
    )
