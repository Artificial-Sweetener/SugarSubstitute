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

"""Contract tests for the projection-engine segment reorder overlay."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea, QVBoxLayout, QWidget

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptSyntaxProfileService,
    PromptSyntaxService,
)
from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.models import (
    PromptReorderCommitIntent,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionDocument,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptReorderView,
    SegmentReorderOverlay,
)
from substitute.presentation.editor.prompt_editor.composition.reorder_overlay_factory import (
    PromptSegmentReorderOverlayFactory,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview import (
    PromptReorderPreviewState,
    PromptReorderProjectionSnapshot,
)
from tests.prompt_projection_test_helpers import surface_for
from tests.execution_test_helpers import immediate_prompt_task_executor_factory

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "segment reorder overlay tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _EmptyPromptAutocompleteGateway:
    """Return deterministic empty autocomplete results for reorder tests."""

    @staticmethod
    def search(
        _prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no autocomplete suggestions for the supplied prefix."""

        _ = limit
        return ()


class _EmptyPromptWildcardCatalogGateway:
    """Return deterministic missing wildcard rows for reorder overlay tests."""

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
        """Return missing rows for the supplied wildcard references."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=False,
            )
            for reference in references
        )


def ensure_qapp() -> QApplication:
    """Return a running Qt application for reorder overlay tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication, cycles: int = 5) -> None:
    """Flush a few event-loop turns so widget state and geometry settle."""

    for _ in range(cycles):
        app.processEvents()


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
    overlay = PromptSegmentReorderOverlayFactory(
        document_service=document_service,
        syntax_service=syntax_service,
        syntax_profile=syntax_profile,
    ).create_segment_overlay(editor, layout_policy=document_service)
    _connect_preview_sync(
        editor,
        overlay,
        document_service=document_service,
        syntax_service=syntax_service,
        syntax_profile=syntax_profile,
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
    return editor, overlay


def _chip_widgets(overlay: QWidget) -> list[QWidget]:
    """Return visible reorder chips sorted by their rendered position."""

    chips = [
        chip
        for chip in overlay.findChildren(QWidget, "segmentChip")
        if chip.isVisible()
    ]
    return sorted(
        chips,
        key=lambda chip: (
            chip.mapToGlobal(chip.rect().topLeft()).y(),
            chip.mapToGlobal(chip.rect().topLeft()).x(),
        ),
    )


def _chip_by_segment_index(overlay: QWidget, segment_index: int) -> QWidget:
    """Return one rendered chip by its segment index property."""

    for chip in overlay.findChildren(QWidget, "segmentChip"):
        if chip.property("segmentIndex") == segment_index:
            return chip
    raise AssertionError(f"Missing chip for segment index {segment_index}.")


def _chip_text(chip: QWidget) -> str:
    """Return the segment label recorded on one reorder hotspot widget."""

    segment_text = chip.property("segmentText")
    assert isinstance(segment_text, str)
    return segment_text


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
    chip: QWidget,
    *,
    global_target: QPoint,
) -> None:
    """Drag one reorder hotspot to the supplied global target point."""

    start = chip.rect().center()
    target = chip.mapFromGlobal(global_target)
    QTest.mousePress(chip, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(chip, target, 10)
    QTest.mouseRelease(chip, Qt.MouseButton.LeftButton, pos=target, delay=10)


def _connect_preview_sync(
    editor: PromptEditor,
    overlay: SegmentReorderOverlay,
    *,
    document_service: PromptDocumentService,
    syntax_service: PromptSyntaxService,
    syntax_profile: object,
) -> None:
    """Mirror the controller's preview-state synchronization for direct overlay tests."""

    def _sync_preview_state() -> None:
        """Push one overlay preview update through the editor surface."""

        preview_layout_view = overlay.preview_layout_view()
        base_drag_layout_view = overlay.base_drag_layout_view()
        ordered_chip_indices = tuple(overlay.ordered_chip_indices())
        if preview_layout_view is None and base_drag_layout_view is None:
            overlay.set_preview_snapshot(
                None,
                base_drag_snapshot=None,
                ordered_chip_indices=ordered_chip_indices,
            )
            editor.clear_reorder_preview_state()
            return
        document_view = cast(Any, overlay)._document_view
        assert document_view is not None
        if preview_layout_view is None:
            current_layout_view = cast(Any, overlay)._current_layout_view
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
                dragged_chip_index=overlay.dragged_segment_index(),
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
    document_view = cast(Any, overlay)._document_view
    assert document_view is not None
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


def test_segment_reorder_overlay_builds_chip_widgets_inside_editor_viewport(
    widgets: list[QWidget],
) -> None:
    """Parsed segment views should become chip widgets inside the editor viewport."""

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

    _editor, overlay = _create_overlay(
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
    assert len(view.render_state.live_chips) == 3
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
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    process_events(app)

    assert dragged_chip.cursor().shape() == Qt.CursorShape.ClosedHandCursor

    QTest.mouseRelease(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
        delay=10,
    )
    process_events(app)

    assert dragged_chip.cursor().shape() == Qt.CursorShape.OpenHandCursor


def test_segment_reorder_overlay_keeps_drag_proxy_above_pointer(
    widgets: list[QWidget],
) -> None:
    """The held chip proxy should stay near the pointer while sizing itself safely."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="Held, beta, gamma",
    )
    dragged_chip = _chip_by_segment_index(overlay, 0)
    proxy = _drag_proxy(overlay)
    target_global = dragged_chip.mapToGlobal(
        dragged_chip.rect().center() + QPoint(80, 18)
    )

    assert proxy.testAttribute(Qt.WidgetAttribute.WA_StyledBackground) is False
    assert proxy.inherits("QFrame") is True

    QTest.mousePress(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip, dragged_chip.mapFromGlobal(target_global), 10)
    process_events(app)

    proxy_parent = proxy.parentWidget()
    assert proxy_parent is not None
    pointer_in_proxy_host = proxy_parent.mapFromGlobal(target_global)

    assert proxy.isVisible() is True
    assert proxy.parentWidget() is not overlay
    assert proxy.width() > 0
    assert proxy.height() > 0
    assert (
        proxy.geometry().left() <= pointer_in_proxy_host.x() <= proxy.geometry().right()
    )
    assert -2 <= proxy.geometry().bottom() - pointer_in_proxy_host.y() <= 6
    proxy_mask = proxy.mask()
    assert proxy_mask.contains(proxy.rect().center()) is True
    assert proxy_mask.contains(QPoint(0, 0)) is False

    QTest.mouseRelease(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(target_global),
        delay=10,
    )
    process_events(app)

    assert proxy.isVisible() is False


def test_segment_reorder_overlay_drag_proxy_can_escape_overlay_bounds(
    widgets: list[QWidget],
) -> None:
    """The floating drag proxy should only escape the prompt viewport by a small bounded margin."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="Held, beta, gamma",
    )
    dragged_chip = _chip_by_segment_index(overlay, 0)
    proxy = _drag_proxy(overlay)
    target_global = overlay.mapToGlobal(
        QPoint(overlay.width() // 2, overlay.height() + 40)
    )

    QTest.mousePress(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip, dragged_chip.mapFromGlobal(target_global), 10)
    process_events(app)

    proxy_bottom_global = proxy.mapToGlobal(proxy.rect().bottomLeft()).y()
    overlay_bottom_global = overlay.mapToGlobal(overlay.rect().bottomLeft()).y()

    assert proxy.isVisible() is True
    assert proxy_bottom_global > overlay_bottom_global
    assert proxy_bottom_global <= overlay_bottom_global + 20

    QTest.mouseRelease(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(target_global),
        delay=10,
    )
    process_events(app)


def test_segment_reorder_overlay_cancel_restores_drag_state(
    widgets: list[QWidget],
) -> None:
    """Cancel should restore public drag state without mutating source text."""

    app = ensure_qapp()
    editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="alpha, beta, gamma",
    )
    dragged_chip = _chip_by_segment_index(overlay, 1)
    first_chip = _chip_by_segment_index(overlay, 0)
    proxy = _drag_proxy(overlay)
    target_global = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )

    QTest.mousePress(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip, dragged_chip.mapFromGlobal(target_global), 10)
    process_events(app)

    assert overlay.dragged_segment_index() == 1
    assert proxy.isVisible() is True

    overlay.cancel_drag()
    process_events(app)

    assert editor.toPlainText() == "alpha, beta, gamma"
    assert overlay.dragged_segment_index() is None
    assert overlay.drop_target() is None
    assert overlay.ordered_chip_indices() == [0, 1, 2]
    assert overlay.has_reordered() is False
    pointer_state = overlay.pointer_reorder_state()
    preview_state = overlay.preview_target_state()
    assert pointer_state.dragged_segment_index is None
    assert pointer_state.active_drop_target is None
    assert preview_state.active_target is None
    assert preview_state.has_preview_layout is False
    assert proxy.isVisible() is False

    QTest.mouseRelease(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(target_global),
        delay=10,
    )
    process_events(app)


def test_segment_reorder_overlay_uses_projection_engine_for_preview_and_drag_proxy(
    widgets: list[QWidget],
) -> None:
    """Dragging emphasized text should keep projection tokens in preview and proxy."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=340,
        height=180,
        text="(1girl:0.05), solo",
    )
    emphasized_chip = _chip_by_segment_index(overlay, 0)
    solo_chip = _chip_by_segment_index(overlay, 1)
    drag_target = overlay.mapToGlobal(
        QPoint(overlay.width() - 8, solo_chip.rect().center().y())
    )

    QTest.mousePress(
        emphasized_chip,
        Qt.MouseButton.LeftButton,
        pos=emphasized_chip.rect().center(),
    )
    QTest.mouseMove(emphasized_chip, emphasized_chip.mapFromGlobal(drag_target), 10)
    process_events(app)

    preview_projection_document = _preview_projection_document(overlay)
    drag_proxy_projection_document = _drag_proxy_projection_document(overlay)

    assert _preview_text(overlay) == "solo, (1girl:0.05)"
    assert preview_projection_document is not None
    assert drag_proxy_projection_document is not None
    assert any(
        token.kind is PromptProjectionTokenKind.EMPHASIS
        and token.display_text == "1girl"
        and token.value_text == "0.05"
        for token in cast(Any, preview_projection_document).tokens
    )
    assert any(
        token.kind is PromptProjectionTokenKind.EMPHASIS
        and token.display_text == "1girl"
        and token.value_text == "0.05"
        for token in cast(Any, drag_proxy_projection_document).tokens
    )

    QTest.mouseRelease(
        emphasized_chip,
        Qt.MouseButton.LeftButton,
        pos=emphasized_chip.mapFromGlobal(drag_target),
        delay=10,
    )
    process_events(app)


def test_segment_reorder_overlay_drag_proxy_projects_lora_without_banners(
    widgets: list[QWidget],
) -> None:
    """Dragging a LoRA chip should keep the proxy projected while suppressing banners."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="<lora:Mineru:0.80>, solo",
    )
    lora_chip = _chip_by_segment_index(overlay, 0)
    solo_chip = _chip_by_segment_index(overlay, 1)
    drag_target = overlay.mapToGlobal(
        QPoint(overlay.width() - 8, solo_chip.rect().center().y())
    )

    QTest.mousePress(
        lora_chip,
        Qt.MouseButton.LeftButton,
        pos=lora_chip.rect().center(),
    )
    QTest.mouseMove(lora_chip, lora_chip.mapFromGlobal(drag_target), 10)
    process_events(app)

    drag_proxy_projection_document = _drag_proxy_projection_document(overlay)
    text_paint_payload = _drag_proxy_text_paint_payload(overlay)
    assert text_paint_payload is not None
    lora_renderer = cast(
        Any, text_paint_payload
    ).layout.inline_object_renderers.renderer_for("lora_chip")

    assert drag_proxy_projection_document is not None
    assert any(
        token.kind is PromptProjectionTokenKind.LORA
        and token.display_text == "Mineru"
        and token.value_text == "0.80"
        for token in cast(Any, drag_proxy_projection_document).tokens
    )
    assert cast(bool, getattr(lora_renderer, "_suppress_banners")) is True

    QTest.mouseRelease(
        lora_chip,
        Qt.MouseButton.LeftButton,
        pos=lora_chip.mapFromGlobal(drag_target),
        delay=10,
    )
    process_events(app)


def test_segment_reorder_overlay_splits_multi_tag_emphasis_shell_into_multiple_chips(
    widgets: list[QWidget],
) -> None:
    """Alt chip visuals should expose one chip per prompt tag inside an exact shell."""

    _editor, overlay = _create_overlay(
        widgets,
        width=520,
        height=180,
        text="(1girl, solo:1.10), blush",
    )

    chips = _chip_widgets(overlay)

    assert [_chip_text(chip) for chip in chips] == ["1girl,", "solo,", "blush"]


def test_segment_reorder_overlay_expands_preview_and_drag_proxy_for_split_emphasis_chip(
    widgets: list[QWidget],
) -> None:
    """Separated emphasis chips should size preview and proxy bubbles to the standalone shell."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=520,
        height=180,
        text="(1girl, solo:1.10), blush",
    )
    solo_chip = _chip_by_segment_index(overlay, 1)
    blush_chip = _chip_by_segment_index(overlay, 2)
    drag_target = overlay.mapToGlobal(
        QPoint(overlay.width() - 8, blush_chip.rect().center().y())
    )
    original_chip_width = solo_chip.width()

    QTest.mousePress(
        solo_chip,
        Qt.MouseButton.LeftButton,
        pos=solo_chip.rect().center(),
    )
    QTest.mouseMove(solo_chip, solo_chip.mapFromGlobal(drag_target), 10)
    process_events(app)

    preview_rect = _preview_rect(overlay, 1)
    proxy = _drag_proxy(overlay)

    assert _preview_text(overlay) == "(1girl:1.10), blush, (solo:1.10)"
    assert preview_rect is not None
    assert preview_rect.width() > original_chip_width
    assert proxy.width() > original_chip_width

    QTest.mouseRelease(
        solo_chip,
        Qt.MouseButton.LeftButton,
        pos=solo_chip.mapFromGlobal(drag_target),
        delay=10,
    )
    process_events(app)


def test_segment_reorder_overlay_landing_preview_uses_outline_without_redrawing_text(
    widgets: list[QWidget],
) -> None:
    """Landing previews should reuse bubble geometry without repainting dragged text."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=320,
        height=180,
        text="alpha, beta, gamma",
    )
    first_chip = _chip_by_segment_index(overlay, 0)
    second_chip = _chip_by_segment_index(overlay, 1)
    drag_target = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )

    QTest.mousePress(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    QTest.mouseMove(second_chip, second_chip.mapFromGlobal(drag_target), 10)
    process_events(app)

    painted_text_calls: list[bool] = []
    view = overlay.findChild(PromptReorderView, "segmentReorderView")
    assert view is not None
    original_paint_projection_text = cast(
        Any, view
    )._projection_chip_painter.paint_projection_text

    def recording_paint_projection_text(*args: object, **kwargs: object) -> object:
        """Record any accidental overlay-owned text painting during landing preview."""

        painted_text_calls.append(True)
        return original_paint_projection_text(*args, **kwargs)

    cast(
        Any, view
    )._projection_chip_painter.paint_projection_text = recording_paint_projection_text

    overlay.repaint()
    process_events(app)

    assert _preview_rect(overlay, 1) is not None
    assert painted_text_calls == []

    QTest.mouseRelease(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(drag_target),
        delay=10,
    )
    process_events(app)


def test_segment_reorder_overlay_keeps_preview_geometry_for_long_drag(
    widgets: list[QWidget],
) -> None:
    """Long-prompt drag target changes should keep complete preview geometry."""

    app = ensure_qapp()
    text = ", ".join(f"tag{i:03d}" for i in range(130))
    _editor, overlay = _create_overlay(
        widgets,
        width=720,
        height=260,
        text=text,
    )
    first_chip = _chip_by_segment_index(overlay, 0)
    second_chip = _chip_by_segment_index(overlay, 1)
    preview_signal_count = 0

    def record_preview_signal() -> None:
        """Record preview sync requests emitted after the test drag starts."""

        nonlocal preview_signal_count
        preview_signal_count += 1

    overlay.previewLayoutChanged.connect(record_preview_signal)
    drag_target = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )

    QTest.mousePress(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    QTest.mouseMove(second_chip, second_chip.mapFromGlobal(drag_target), 10)
    process_events(app)

    assert preview_signal_count >= 2
    assert overlay.drop_target() is not None
    assert overlay.ordered_chip_indices()[0] == 1
    assert _preview_rect(overlay, 1) is not None


def test_segment_reorder_overlay_position_refresh_key_tracks_viewport_changes(
    widgets: list[QWidget],
) -> None:
    """The cheap position key should skip unchanged viewports and catch resizes."""

    app = ensure_qapp()
    editor, overlay = _create_overlay(
        widgets,
        width=360,
        height=180,
        text="alpha, beta, gamma",
    )

    assert overlay.needs_position_refresh(reason="unchanged") is False

    host = editor.parentWidget()
    assert host is not None
    host.resize(420, 220)
    process_events(app)

    assert overlay.needs_position_refresh(reason="resized") is True


def test_segment_reorder_overlay_preserves_grab_offset_in_drag_intent_rect(
    widgets: list[QWidget],
) -> None:
    """Held-chip target geometry should preserve the original pointer grab offset."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=560,
        height=180,
        text="wide descriptive chip, beta, gamma",
    )
    dragged_chip = _chip_by_segment_index(overlay, 0)
    chip_geometry = dragged_chip.geometry()
    press_pos = QPoint(max(1, dragged_chip.width() - 5), dragged_chip.height() // 2)
    move_global = dragged_chip.mapToGlobal(press_pos + QPoint(48, 0))

    QTest.mousePress(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=press_pos,
    )
    QTest.mouseMove(dragged_chip, dragged_chip.mapFromGlobal(move_global), 10)
    process_events(app)

    intent_rect = overlay.pointer_reorder_state().last_drag_intent_rect
    assert intent_rect is not None
    press_overlay_pos = QPointF(dragged_chip.mapTo(overlay, press_pos))
    grabbed_offset = press_overlay_pos - QPointF(chip_geometry.topLeft())
    expected_top_left = QPointF(overlay.mapFromGlobal(move_global)) - grabbed_offset

    assert abs(intent_rect.topLeft().x() - expected_top_left.x()) < 0.01
    assert abs(intent_rect.topLeft().y() - expected_top_left.y()) < 0.01
    assert intent_rect.size().toSize() == chip_geometry.size()

    QTest.mouseRelease(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(move_global),
        delay=10,
    )
    process_events(app)


def test_segment_reorder_overlay_updates_visual_order_across_wrapped_rows(
    widgets: list[QWidget],
) -> None:
    """Dragging a chip between wrapped rows should update the overlay order."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=220,
        height=180,
        text="alpha, beta, gamma, delta",
    )

    chips = _chip_widgets(overlay)
    assert len({chip.geometry().top() for chip in chips}) > 1

    dragged_chip = _chip_by_segment_index(overlay, 3)
    target_chip = _chip_by_segment_index(overlay, 1)
    _drag_chip_to_global(
        dragged_chip,
        global_target=target_chip.mapToGlobal(
            QPoint(4, max(4, target_chip.rect().center().y()))
        ),
    )
    process_events(app)

    assert overlay.ordered_chip_indices() == [0, 3, 1, 2]
    assert overlay.has_reordered() is True


def test_segment_reorder_overlay_uses_editor_scrollbar_for_long_prompts(
    widgets: list[QWidget],
) -> None:
    """Long prompts should keep the editor scrollbar as the only scroll surface."""

    editor, overlay = _create_overlay(
        widgets,
        width=260,
        height=120,
        text=", ".join(
            f"long segment {index} with extra detail" for index in range(14)
        ),
    )

    chip_rows = {chip.geometry().top() for chip in _chip_widgets(overlay)[:4]}

    assert editor.verticalScrollBar().maximum() > 0
    assert len(chip_rows) > 1
    assert overlay.findChild(QScrollArea, "segmentReorderScrollArea") is None
    assert overlay.findChild(QWidget, "segmentReorderFrame") is None


def test_segment_reorder_overlay_reports_no_reorder_when_drag_stays_in_place(
    widgets: list[QWidget],
) -> None:
    """Starting and ending a drag in the same slot should remain a no-op."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="alpha, beta, gamma",
    )

    dragged_chip = _chip_by_segment_index(overlay, 1)
    QTest.mouseClick(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    process_events(app)

    assert overlay.ordered_chip_indices() == [0, 1, 2]
    assert overlay.has_reordered() is False
    assert overlay.dragged_segment_index() is None


def test_segment_reorder_overlay_emits_typed_pointer_drop_snapshot(
    widgets: list[QWidget],
) -> None:
    """Pointer drops should publish prepared reorder state as a typed intent."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="alpha, beta, gamma",
    )
    commit_intents: list[PromptReorderCommitIntent] = []
    overlay.set_commit_handler(commit_intents.append)

    dragged_chip = _chip_by_segment_index(overlay, 1)
    first_chip = _chip_by_segment_index(overlay, 0)
    drag_target = first_chip.mapToGlobal(QPoint(4, max(4, first_chip.height() // 2)))
    QTest.mousePress(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip, dragged_chip.mapFromGlobal(drag_target), 10)
    QTest.mouseRelease(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(drag_target),
    )
    process_events(app)

    assert len(commit_intents) == 1
    intent = commit_intents[0]
    assert intent.reason == "pointer_drop"
    assert intent.snapshot is not None
    assert intent.snapshot.has_reordered is True
    assert intent.snapshot.ordered_chip_indices == tuple(overlay.ordered_chip_indices())
    assert intent.snapshot.layout_view is overlay.current_layout_view()


def test_segment_reorder_overlay_autoscrolls_editor_scrollbar_while_dragging_near_viewport_edge(
    widgets: list[QWidget],
) -> None:
    """Dragging near the viewport edge should advance the editor scrollbar."""

    app = ensure_qapp()
    editor, overlay = _create_overlay(
        widgets,
        width=240,
        height=120,
        text=", ".join(
            f"segment {index} with a longer description" for index in range(12)
        ),
    )

    scrollbar = editor.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(0)
    process_events(app)

    dragged_chip = _chip_by_segment_index(overlay, 0)
    initial_scroll_value = scrollbar.value()
    QTest.mousePress(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(
        dragged_chip,
        dragged_chip.mapFromGlobal(
            overlay.mapToGlobal(QPoint(overlay.width() // 2, overlay.height() - 2))
        ),
        10,
    )
    process_events(app)
    QTest.qWait(120)
    QTest.mouseRelease(
        dragged_chip,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(
            overlay.mapToGlobal(QPoint(overlay.width() // 2, overlay.height() - 2))
        ),
        delay=10,
    )
    process_events(app)

    assert scrollbar.value() > initial_scroll_value
