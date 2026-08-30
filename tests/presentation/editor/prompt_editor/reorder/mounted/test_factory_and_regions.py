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

"""Verify mounted prompt reorder factory and regions."""

from __future__ import annotations

from typing import Any, cast


from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QScrollArea, QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfileService,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptReorderView,
)
from substitute.presentation.editor.prompt_editor.composition.reorder_overlay_factory import (
    PromptSegmentReorderOverlayFactory,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from tests.support.prompt_editor.projection_engine_support import surface_for

from .gateway_support import (
    _EmptyPromptWildcardCatalogGateway,
)
from .mount_support import (
    ensure_qapp,
    process_events,
    _create_editor,
    _create_overlay,
    _pointer_regions,
    _chip_by_segment_index,
    _chip_text,
    _chip_segment_index,
)


def test_segment_overlay_factory_returns_ready_preview_ports_before_activation() -> (
    None
):
    """Factory composition must publish ready preview ports before session entry."""

    widgets: list[QWidget] = []
    editor = _create_editor(
        widgets,
        width=640,
        height=360,
        text="alpha, beta",
    )
    document_service = PromptDocumentService()
    assembly = PromptSegmentReorderOverlayFactory(
        document_service=document_service,
        syntax_service=PromptSyntaxService(_EmptyPromptWildcardCatalogGateway()),
        syntax_profile=PromptSyntaxProfileService().default_profile(),
        geometry_owner=surface_for(editor).reorder_geometry_owner,
        interaction_metrics=PromptReorderInteractionMetricsOwner(),
    ).create_segment_overlay(editor, layout_policy=document_service)

    assert assembly.preview_build_facts.snapshot().dragged_segment_index is None
    assert assembly.preview_sync_context.snapshot().dragged_segment_index is None

    assembly.overlay.close()
    for widget in widgets:
        widget.close()


def test_segment_reorder_overlay_materializes_only_viewport_pointer_regions(
    widgets: list[QWidget],
) -> None:
    """Large documents should own logical regions only for visible chip geometry."""

    app = ensure_qapp()
    segment_count = 200
    editor, overlay = _create_overlay(
        widgets,
        width=240,
        height=120,
        text=", ".join(
            f"segment {index} with a longer description"
            for index in range(segment_count)
        ),
    )

    initial_indices = {_chip_segment_index(chip) for chip in _pointer_regions(overlay)}
    initial_visual_indices = set(cast(Any, overlay)._live_visual_owner.visuals_by_index)

    assert initial_indices == initial_visual_indices
    assert overlay.findChildren(QWidget, "segmentChip") == []
    assert 0 < len(initial_indices) < segment_count

    editor.verticalScrollBar().setValue(editor.verticalScrollBar().maximum())
    overlay.refresh_geometry(reason="test_scroll")
    process_events(app)

    scrolled_indices = {_chip_segment_index(chip) for chip in _pointer_regions(overlay)}
    scrolled_visual_indices = set(
        cast(Any, overlay)._live_visual_owner.visuals_by_index
    )
    assert scrolled_indices == scrolled_visual_indices
    assert overlay.findChildren(QWidget, "segmentChip") == []
    assert 0 < len(scrolled_indices) < segment_count
    assert scrolled_indices != initial_indices


def test_segment_reorder_overlay_builds_pointer_regions_inside_editor_viewport(
    widgets: list[QWidget],
) -> None:
    """Parsed segment views should become pointer regions inside the viewport."""

    editor, overlay = _create_overlay(
        widgets,
        width=520,
        height=220,
        text='alpha, "beta, gamma", [delta, epsilon],',
        active_segment_index=1,
    )

    assert overlay.parentWidget() is editor.viewport()
    assert _chip_text(_chip_by_segment_index(overlay, 0)) == "alpha,"
    assert _chip_text(_chip_by_segment_index(overlay, 1)) == '"beta, gamma",'
    assert _chip_text(_chip_by_segment_index(overlay, 2)) == "[delta, epsilon],"
    assert bool(_chip_by_segment_index(overlay, 1).property("active")) is True
    assert overlay.findChild(QScrollArea, "segmentReorderScrollArea") is None
    assert overlay.findChild(QWidget, "segmentReorderFrame") is None


def test_segment_reorder_overlay_hosts_passive_reorder_view(
    widgets: list[QWidget],
) -> None:
    """The overlay should host reorder painting in a passive child view."""

    editor, overlay = _create_overlay(
        widgets,
        width=320,
        height=180,
        text="alpha, beta, gamma",
    )

    view = overlay.findChild(PromptReorderView, "segmentReorderView")

    assert view is not None
    assert view.parentWidget() is overlay
    assert view.geometry() == overlay.rect()
    assert view.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert view.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert view.render_state.live_chips == ()
    surface_chrome = cast(
        Any, editor
    )._surface._reorder_surface_visual_state.state.chrome_snapshot
    assert surface_chrome is not None
    assert len(surface_chrome.chips) == 3
    assert view.render_state.preview_active is False


def test_segment_reorder_overlay_uses_real_grab_cursors(
    widgets: list[QWidget],
) -> None:
    """Chips should expose immediate closed-hand press feedback and drag cursors."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="alpha, beta, gamma",
    )
    dragged_chip = _chip_by_segment_index(overlay, 1)

    assert overlay.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert dragged_chip.cursor().shape() == Qt.CursorShape.OpenHandCursor

    QTest.mousePress(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    process_events(app)

    assert dragged_chip.cursor().shape() == Qt.CursorShape.ClosedHandCursor

    QTest.mouseRelease(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
        delay=10,
    )
    process_events(app)

    assert dragged_chip.cursor().shape() == Qt.CursorShape.OpenHandCursor
