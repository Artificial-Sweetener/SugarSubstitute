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

"""Characterize the read-only CuteCanvas Output document boundary."""

from __future__ import annotations

from typing import Protocol, cast
from uuid import UUID, uuid4

from pytest import MonkeyPatch, approx
from PySide6.QtCore import QEvent, QLineF, QPoint, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QImage,
    QMouseEvent,
    QWheelEvent,
)
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from cutecanvas import (
    CanvasComparison,
    CanvasComparisonDivider,
    CanvasComparisonOverlayState,
    CanvasComparisonScale,
    CanvasComparisonZoomGesture,
    ComparisonOrientation,
    DragSubject,
)
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
    bind_output_canvas_session,
)
from substitute.application.workflows.output_detail_inspection import (
    OutputDetailInspectionGroup,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewAcceptance,
    OutputPreviewLane,
    OutputPreviewLaneKey,
    OutputPreviewRegistry,
)
from substitute.application.ports import PreviewImageUpdate
from substitute.application.workflows.output_visual_events import LivePreviewEvent
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from substitute.presentation.canvas.output.output_context_menu_composition import (
    compose_output_context_menu,
)
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.output.output_compare_material_gap import (
    OutputCompareMaterialGapCoordinator,
)
from substitute.presentation.shell.chrome_style import (
    body_material_wash_color,
    resolved_backdrop_mode,
)
from substitute.presentation.canvas.output import (
    output_canvas_context_menu,
    output_grid_context_menu,
)
from substitute.presentation.canvas.shared.canvas_zoom_indicator import (
    CANVAS_ZOOM_INDICATOR_OVERLAY_NAME,
)
from substitute.presentation.resources.fluent_app_icon import AppIcon
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel


class _ZoomModeProbe(Protocol):
    """Describe the zoom-mode value exposed by a native comparison viewport."""

    value: str


class _ViewportProbe(Protocol):
    """Describe renderer-neutral viewport observations used by the fixture."""

    def get_zoom_mode(self) -> _ZoomModeProbe:
        """Return the active zoom interpretation."""

    def computeFitZoom(self) -> float:  # noqa: N802
        """Return the fit scale for the mounted comparison."""

    def setZoomAndPan(self, zoom: float, pan: QPointF) -> None:  # noqa: N802
        """Apply an exact mounted comparison viewport."""


class _CatalogEntryProbe(Protocol):
    """Describe one catalog entry used to verify the presented pair."""

    entry_id: UUID


class _CatalogProbe(Protocol):
    """Describe catalog state observable through the native test surface."""

    entries: tuple[_CatalogEntryProbe, ...]
    current: _CatalogEntryProbe | None


class _ComparisonStateProbe(Protocol):
    """Describe comparison state observable through the native test surface."""

    source_id: UUID | None
    split_position: float
    orientation: ComparisonOrientation


class _LinkedGroupProbe(Protocol):
    """Describe one renderer-neutral linked inspection group."""

    members: tuple[UUID, ...]


class _DividerStateProbe(Protocol):
    """Describe mounted divider geometry needed by interaction tests."""

    enabled: bool
    dragging: bool
    full_segment: QLineF | None
    visible_segment: QLineF | None


class _NativeComparisonProbe(Protocol):
    """Describe comparison observations without importing the QPane renderer."""

    viewport: _ViewportProbe

    def catalog(self) -> _CatalogProbe:
        """Return the mounted comparison catalog."""

    def comparisonState(self) -> _ComparisonStateProbe:  # noqa: N802
        """Return the mounted comparison state."""

    def linkedImageGroups(self) -> tuple[_LinkedGroupProbe, ...]:  # noqa: N802
        """Return renderer-neutral linked inspection groups."""

    def applyZoom(self, requested_zoom: float) -> None:  # noqa: N802
        """Apply one exact comparison zoom."""

    def currentZoom(self) -> float:  # noqa: N802
        """Return the mounted comparison zoom."""

    def currentPan(self) -> QPointF:  # noqa: N802
        """Return the mounted comparison pan."""

    def comparisonDividerState(self) -> _DividerStateProbe:  # noqa: N802
        """Return mounted divider geometry."""

    def setZoomFit(self) -> None:  # noqa: N802
        """Fit the mounted comparison."""


def _image(color: str) -> QImage:
    """Return one non-null output image with a deterministic color."""

    image = QImage(QSize(32, 24), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(color))
    return image


def _sized_image(color: str, size: QSize) -> QImage:
    """Return one deterministic Output image with explicit source dimensions."""

    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(color))
    return image


def _app() -> QApplication:
    """Return a QApplication before constructing one Output workspace."""

    application = QApplication.instance()
    return application if isinstance(application, QApplication) else QApplication([])


class _DragProvider:
    """Capture output drag subjects without starting a native drag."""

    def __init__(self) -> None:
        """Initialize the captured subject collection."""
        self.subjects: list[object] = []

    def materialize(self, subject: object, _complete: object) -> None:
        """Capture the subject requested by the real pointer gesture."""
        self.subjects.append(subject)


class _ZoomOverlayPainter:
    """Record Output percentage badges painted through the public overlay hook."""

    def __init__(self) -> None:
        """Initialize the recorded overlay operations."""

        self.texts: list[str] = []
        self.bounds: list[QRectF] = []
        self._opacity = 1.0

    def save(self) -> None:
        """Accept the painter save operation."""

    def restore(self) -> None:
        """Accept the painter restore operation."""

    def opacity(self) -> float:
        """Return the current painter opacity."""

        return self._opacity

    def setOpacity(self, opacity: float) -> None:  # noqa: N802
        """Record the current painter opacity."""

        self._opacity = opacity

    def setRenderHint(self, *_args: object) -> None:  # noqa: N802
        """Accept the antialiasing render hint."""

    def setFont(self, *_args: object) -> None:  # noqa: N802
        """Accept the established percentage-label font."""

    def setBrush(self, *_args: object) -> None:  # noqa: N802
        """Accept the established overlay material brush."""

    def setPen(self, *_args: object) -> None:  # noqa: N802
        """Accept the established overlay border and text pens."""

    def drawRoundedRect(self, bounds: QRectF, *_args: object) -> None:  # noqa: N802
        """Record one painted badge background."""

        self.bounds.append(QRectF(bounds))

    def drawText(self, _bounds: object, _alignment: object, text: str) -> None:  # noqa: N802
        """Record one painted percentage label."""

        self.texts.append(text)


def _wait_for_rendered_color(
    application: QApplication,
    target: QWidget,
    expected: QColor,
) -> bool:
    """Return whether an offscreen target renders the admitted image color."""

    for _attempt in range(100):
        application.processEvents()
        image = target.grab().toImage()
        if not image.isNull():
            sampled = image.pixelColor(image.width() // 2, image.height() // 2)
            if sampled == expected:
                return True
        QTest.qWait(5)
    return False


def _wheel_event(target: QWidget, position: QPointF) -> QWheelEvent:
    """Create one local wheel gesture for a public Output canvas surface."""

    global_position = QPointF(target.mapToGlobal(position.toPoint()))
    return QWheelEvent(
        position,
        global_position,
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def _wait_for_comparison_colors(
    application: QApplication,
    target: QWidget,
    *,
    primary: QColor,
    secondary: QColor,
) -> bool:
    """Return whether one native reveal pane renders both admitted source colors."""

    for _attempt in range(100):
        application.processEvents()
        image = target.grab().toImage()
        if not image.isNull():
            left = image.pixelColor(image.width() // 4, image.height() // 2)
            right = image.pixelColor(3 * image.width() // 4, image.height() // 2)
            if left == primary and right == secondary:
                return True
        QTest.qWait(5)
    return False


def _assert_rendered_horizontal_seam(
    workspace: object,
    x: int,
    seam_y: int,
    expected_gap: int,
) -> None:
    """Require the visible grid seam to contain one stable raster gap."""

    grab = getattr(workspace, "grab")
    image = grab().toImage()
    assert not image.isNull()
    upper = image.pixelColor(x, seam_y - 1)
    lower = image.pixelColor(x, seam_y + expected_gap)
    assert upper == QColor("red")
    sampled_rows = ", ".join(
        f"{row}:{image.pixelColor(x, row).name()}"
        for row in range(seam_y - 2, seam_y + expected_gap + 24)
    )
    assert lower == QColor("red"), sampled_rows
    assert all(
        image.pixelColor(x, y) != QColor("red")
        for y in range(seam_y, seam_y + expected_gap)
    )


def test_output_document_owns_locked_compositions_and_presentations() -> None:
    """Map application images to read-only compositions across Output views."""

    _app()
    document = OutputCanvasDocument()
    first_id = uuid4()
    second_id = uuid4()
    first_image = _image("red")
    second_image = _image("blue")

    try:
        assert document.admit_image(first_id, first_image)
        assert document.admit_image(second_id, second_image)
        assert not document.admit_image(first_id, first_image)

        first_composition = document.composition_id_for(first_id)
        second_composition = document.composition_id_for(second_id)
        assert first_composition is not None
        assert second_composition is not None

        document.present_single(first_id)
        single_presentation = document.workspace.session.presentation
        assert single_presentation.target_ids == (first_composition,)
        assert document.workspace.session.inspection.groups() == ()

        document.present_grid((first_id, second_id))
        grid_presentation = document.workspace.session.presentation
        assert grid_presentation.target_ids == (
            first_composition,
            second_composition,
        )
        assert document.workspace.session.inspection.groups() == ()

        document.present_comparison(
            first_id,
            second_id,
            split_position=0.25,
            orientation="horizontal",
        )
        comparison = document.workspace.session.presentation.comparison
        assert comparison is not None
        assert comparison.primary_id == first_composition
        assert comparison.secondary_id == second_composition
        assert comparison.split_position == 0.25
        assert comparison.orientation.value == "horizontal"
        assert document.workspace.session.inspection.groups() == ()

        snapshot = document.document.snapshot()
        first_entry = snapshot.compositions[first_composition]
        assert first_entry.policy.removable
        assert first_entry.layers[0].interaction.selectable is False
        assert first_entry.layers[0].interaction.movable is False
        assert first_entry.layers[0].interaction.pixel_editable is False
        assert first_entry.layers[0].interaction.reorderable is False
        assert first_entry.layers[0].interaction.removable is False
    finally:
        document.close()


def test_output_presentations_keep_grid_detail_and_comparison_viewports_independent() -> (
    None
):
    """Output presentation changes must never transfer viewport state across roles."""

    app = _app()
    document = OutputCanvasDocument()
    image_ids = (uuid4(), uuid4(), uuid4())
    try:
        for image_id, color in zip(image_ids, ("red", "blue", "green"), strict=True):
            assert document.admit_image(image_id, _image(color))
        document.workspace.resize(900, 600)
        document.workspace.show()

        assert document.present_grid(image_ids)
        app.processEvents()
        first_composition = document.composition_id_for(image_ids[0])
        assert first_composition is not None
        grid_canvas = document.workspace.canvasFor(first_composition)
        assert grid_canvas is not None
        grid_zoom = grid_canvas.currentZoom()

        assert document.present_single(image_ids[0])
        app.processEvents()
        detail_canvas = document.workspace.canvasFor(first_composition)
        assert detail_canvas is not None
        assert detail_canvas is not grid_canvas
        detail_canvas.applyZoom(detail_canvas.currentZoom() * 1.5)
        detail_zoom = detail_canvas.currentZoom()

        assert document.present_grid(image_ids)
        app.processEvents()
        assert document.workspace.canvasFor(first_composition) is grid_canvas
        assert grid_canvas.currentZoom() == grid_zoom

        assert document.present_comparison(
            image_ids[0],
            image_ids[1],
            split_position=0.5,
            orientation="vertical",
        )
        app.processEvents()
        second_composition = document.composition_id_for(image_ids[1])
        assert second_composition is not None
        comparison_widget = document.workspace.currentCanvas()
        assert comparison_widget is not None
        assert comparison_widget is not grid_canvas
        assert comparison_widget is not detail_canvas
        comparison_pane = cast(_NativeComparisonProbe, comparison_widget)
        assert tuple(entry.entry_id for entry in comparison_pane.catalog().entries) == (
            first_composition,
            second_composition,
        )
        assert comparison_pane.comparisonState().source_id == second_composition
        assert tuple(
            group.members for group in comparison_pane.linkedImageGroups()
        ) == ((first_composition, second_composition),)
        comparison_pane.applyZoom(comparison_pane.currentZoom() * 1.5)
        app.processEvents()
        assert detail_canvas.currentZoom() == detail_zoom
    finally:
        document.close()
        app.processEvents()


def test_output_comparison_uses_one_native_scene_without_mask_or_geometry_churn() -> (
    None
):
    """Drag the native divider while retaining one fitted QPane viewport widget."""

    app = _app()
    document = OutputCanvasDocument()
    first_id = uuid4()
    second_id = uuid4()
    third_id = uuid4()
    try:
        source_size = QSize(320, 240)
        assert document.admit_image(first_id, _sized_image("red", source_size))
        assert document.admit_image(second_id, _sized_image("blue", source_size))
        assert document.admit_image(third_id, _sized_image("green", source_size))
        document.workspace.resize(900, 600)
        document.workspace.show()
        assert document.present_comparison(
            first_id,
            second_id,
            split_position=0.5,
            orientation="vertical",
        )
        app.processEvents()

        pane_widget = document.workspace.currentCanvas()
        assert pane_widget is not None
        pane = cast(_NativeComparisonProbe, pane_widget)
        assert pane.viewport.get_zoom_mode().value == "fit"
        assert pane.currentZoom() == approx(pane.viewport.computeFitZoom())
        assert _wait_for_comparison_colors(
            app,
            pane_widget,
            primary=QColor("red"),
            secondary=QColor("blue"),
        )
        geometry = pane_widget.geometry()
        assert pane_widget.mask().isEmpty()
        divider = pane.comparisonDividerState()
        assert divider.enabled is True
        assert divider.full_segment is not None
        start = divider.full_segment.pointAt(0.5).toPoint()
        destination = QPoint(
            min(pane_widget.width() - 2, start.x() + 80),
            start.y(),
        )

        QTest.mousePress(pane_widget, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(pane_widget, destination)
        QTest.mouseRelease(
            pane_widget,
            Qt.MouseButton.LeftButton,
            pos=destination,
        )
        app.processEvents()

        assert pane_widget.geometry() == geometry
        assert pane_widget.mask().isEmpty()
        state = pane.comparisonState()
        assert state.split_position > 0.5
        presentation = document.workspace.session.presentation
        assert presentation.comparison is not None
        assert presentation.comparison.split_position == state.split_position
        assert document.present_comparison(
            first_id,
            second_id,
            split_position=state.split_position,
            orientation="horizontal",
        )
        app.processEvents()
        assert document.workspace.currentCanvas() is pane_widget
        assert pane.comparisonState().orientation.value == "horizontal"
        pane.applyZoom(pane.currentZoom() * 1.5)
        pan_before = pane.currentPan()
        pan_start = QPoint(pane_widget.width() // 4, pane_widget.height() // 2)
        pan_destination = pan_start + QPoint(47, 19)
        QTest.mousePress(pane_widget, Qt.MouseButton.LeftButton, pos=pan_start)
        app.sendEvent(
            pane_widget,
            QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(pan_destination),
                QPointF(pane_widget.mapToGlobal(pan_destination)),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        QTest.mouseRelease(
            pane_widget,
            Qt.MouseButton.LeftButton,
            pos=pan_destination,
        )
        app.processEvents()
        comparison_pan = pane.currentPan()
        assert comparison_pan != pan_before
        comparison_zoom = pane.currentZoom()
        assert document.present_comparison(
            second_id,
            third_id,
            split_position=0.4,
            orientation="vertical",
        )
        app.processEvents()
        assert document.workspace.currentCanvas() is pane_widget
        assert _wait_for_comparison_colors(
            app,
            pane_widget,
            primary=QColor("blue"),
            secondary=QColor("green"),
        )
        assert document.present_comparison(
            first_id,
            second_id,
            split_position=state.split_position,
            orientation="vertical",
        )
        app.processEvents()
        restored_widget = document.workspace.currentCanvas()
        assert restored_widget is pane_widget
        assert restored_widget is not None
        restored = cast(_NativeComparisonProbe, restored_widget)
        current_entry = restored.catalog().current
        assert current_entry is not None
        assert current_entry.entry_id == document.composition_id_for(first_id)
        assert restored.comparisonState().source_id == document.composition_id_for(
            second_id
        )
        assert restored.currentZoom() == approx(comparison_zoom)
        restored_pan = restored.currentPan()
        assert restored_pan.x() == approx(comparison_pan.x())
        assert restored_pan.y() == approx(comparison_pan.y())
        restored.setZoomFit()
        assert _wait_for_comparison_colors(
            app,
            restored_widget,
            primary=QColor("red"),
            secondary=QColor("blue"),
        )
    finally:
        document.close()
        app.processEvents()


def test_output_comparison_zoom_stops_when_slower_side_reaches_1000_percent() -> None:
    """Preserve QPane's source-relative comparison ceiling through CuteCanvas."""

    app = _app()
    document = OutputCanvasDocument()
    primary_id = uuid4()
    secondary_id = uuid4()
    try:
        assert document.admit_image(
            primary_id,
            _sized_image("red", QSize(320, 240)),
        )
        assert document.admit_image(
            secondary_id,
            _sized_image("blue", QSize(640, 480)),
        )
        document.workspace.resize(900, 600)
        document.workspace.show()
        assert document.present_comparison(
            primary_id,
            secondary_id,
            split_position=0.5,
            orientation="vertical",
        )
        app.processEvents()

        pane_widget = document.workspace.currentCanvas()
        assert pane_widget is not None
        pane = cast(_NativeComparisonProbe, pane_widget)
        pane.applyZoom(1000.0)
        app.processEvents()

        assert pane.currentZoom() == approx(20.0)
    finally:
        document.close()
        app.processEvents()


def test_output_comparison_preserves_the_original_two_pixel_material_seam() -> None:
    """Keep the two-pixel Output divider on the transformed comparison seam."""

    app = _app()
    document = OutputCanvasDocument()
    first_id = uuid4()
    second_id = uuid4()
    overlay: OutputCompareMaterialGapCoordinator | None = None
    try:
        assert document.admit_image(first_id, _sized_image("red", QSize(640, 480)))
        assert document.admit_image(second_id, _sized_image("blue", QSize(1280, 960)))
        document.workspace.resize(900, 600)
        document.workspace.show()
        assert document.present_comparison(
            first_id,
            second_id,
            split_position=0.35,
            orientation="vertical",
        )
        app.processEvents()

        overlay = OutputCompareMaterialGapCoordinator(document.workspace)
        pane_widget = document.workspace.currentCanvas()
        assert pane_widget is not None
        pane = cast(_NativeComparisonProbe, pane_widget)
        fit_divider = pane.comparisonDividerState()
        assert fit_divider.visible_segment is not None
        fit_divider_x = fit_divider.visible_segment.x1()
        pane.viewport.setZoomAndPan(1.5, QPointF(70.0, -35.0))
        app.processEvents()
        assert _wait_for_comparison_colors(
            app,
            pane_widget,
            primary=QColor("red"),
            secondary=QColor("blue"),
        )
        image = pane_widget.grab().toImage()
        divider = pane.comparisonDividerState()
        assert divider.visible_segment is not None
        assert divider.visible_segment.x1() != approx(fit_divider_x)
        point = divider.visible_segment.pointAt(0.5).toPoint()
        material = QColor(
            *body_material_wash_color(resolved_backdrop_mode(document.workspace))
        )
        seam_colors = [
            image.pixelColor(x, point.y()) for x in range(point.x() - 2, point.x() + 3)
        ]
        assert sum(color.name() == material.name() for color in seam_colors) == 2
        assert QColor("red") in seam_colors
        assert QColor("blue") in seam_colors
    finally:
        if overlay is not None:
            overlay.close()
        document.close()
        app.processEvents()


def test_output_canvas_renders_an_admitted_final_image_offscreen() -> None:
    """Render received final pixels after single-to-grid presentation reflow."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    expected = QColor("red")
    try:
        canvas.resize(640, 480)
        canvas.show()
        assert canvas.document.admit_image(
            first_id,
            _sized_image("red", QSize(960, 1344)),
        )
        assert canvas.document.admit_image(
            second_id,
            _sized_image("blue", QSize(960, 1344)),
        )
        canvas.bind_projection_session(
            _session(boundary, _linked_projection(first_id, second_id))
        )

        composition_id = canvas.document.composition_id_for(first_id)
        second_composition_id = canvas.document.composition_id_for(second_id)
        assert composition_id is not None
        assert second_composition_id is not None
        target = canvas.workspace.canvasFor(composition_id)
        assert target is not None
        assert _wait_for_rendered_color(app, target, expected)
        groups = canvas.workspace.session.inspection.groups()
        assert len(groups) == 1
        assert groups[0].members == (composition_id, second_composition_id)
        target.applyZoom(target.currentZoom() * 1.5)
        canvas.document.present_single(second_id)
        app.processEvents()
        linked_detail = canvas.workspace.canvasFor(second_composition_id)
        assert linked_detail is not None
        assert linked_detail.currentZoom() == approx(target.currentZoom(), rel=1e-12)

        assert canvas.document.present_grid((first_id, second_id))
        assert canvas.document.present_single(first_id)
        assert _wait_for_rendered_color(app, target, expected)
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_output_attaches_a_percentage_overlay_to_every_active_detail_image() -> None:
    """Show the established cursor-relative percentage for each active Output image."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    try:
        canvas.resize(640, 480)
        canvas.show()
        assert canvas.document.admit_image(
            first_id,
            _sized_image("red", QSize(960, 1344)),
        )
        assert canvas.document.admit_image(
            second_id,
            _sized_image("blue", QSize(960, 1344)),
        )
        canvas.bind_projection_session(
            _session(boundary, _projection(first_id, second_id))
        )
        first_composition = canvas.document.composition_id_for(first_id)
        second_composition = canvas.document.composition_id_for(second_id)
        assert first_composition is not None
        assert second_composition is not None
        first_target = canvas.workspace.canvasFor(first_composition)
        assert first_target is not None
        indicators = canvas._zoom_indicators._indicators
        first_indicator = indicators.get(first_target)
        assert first_indicator is not None
        assert CANVAS_ZOOM_INDICATOR_OVERLAY_NAME in first_target.contentOverlays()

        position = QPointF(first_target.rect().center())
        first_zoom = first_target.currentZoom()
        QApplication.sendEvent(first_target, _wheel_event(first_target, position))
        first_target.applyZoom(first_zoom * 1.25)
        app.processEvents()
        assert first_target.currentZoom() > first_zoom
        assert first_indicator.opacity == 1.0

        assert canvas.document.present_single(second_id)
        app.processEvents()
        second_target = canvas.workspace.canvasFor(second_composition)
        assert second_target is not None
        second_indicator = indicators.get(second_target)
        assert second_indicator is not None
        assert CANVAS_ZOOM_INDICATOR_OVERLAY_NAME in second_target.contentOverlays()
        second_position = QPointF(second_target.rect().center())
        second_zoom = second_target.currentZoom()
        QApplication.sendEvent(
            second_target,
            _wheel_event(second_target, second_position),
        )
        second_target.applyZoom(second_zoom * 1.25)
        app.processEvents()
        assert second_target.currentZoom() > second_zoom
        assert second_indicator.opacity == 1.0
    finally:
        canvas.close()
        app.processEvents()


def test_output_comparison_paints_one_percentage_on_each_side_of_the_divider() -> None:
    """Paint independent source-scale badges on their matching comparison sides."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=create_canvas_session_boundary(),
    )
    try:
        assert canvas.document.admit_image(
            first_id,
            _sized_image("red", QSize(32, 24)),
        )
        assert canvas.document.admit_image(
            second_id,
            _sized_image("blue", QSize(64, 24)),
        )
        canvas.resize(800, 600)
        canvas.show()
        assert canvas.document.present_comparison(
            first_id,
            second_id,
            split_position=0.5,
            orientation="vertical",
        )
        app.processEvents()
        first_composition = canvas.document.composition_id_for(first_id)
        second_composition = canvas.document.composition_id_for(second_id)
        assert first_composition is not None
        assert second_composition is not None
        indicator = canvas._zoom_indicators._comparison_indicator
        divider = CanvasComparisonDivider(
            enabled=True,
            split_position=0.5,
            orientation=ComparisonOrientation.VERTICAL,
            visible_segment=QLineF(400.0, 0.0, 400.0, 600.0),
            full_segment=QLineF(400.0, 0.0, 400.0, 600.0),
        )
        canvas.workspace.comparisonZoomGesture.emit(
            CanvasComparisonZoomGesture(QPointF(200.0, 150.0), 1.25)
        )
        painter = _ZoomOverlayPainter()
        indicator.draw(
            painter,
            CanvasComparisonOverlayState(
                comparison=CanvasComparison(
                    first_composition,
                    second_composition,
                    0.5,
                    ComparisonOrientation.VERTICAL,
                ),
                divider=divider,
                viewport=QRect(0, 0, 800, 600),
                primary_scale=CanvasComparisonScale(2.0, 2.0),
                secondary_scale=CanvasComparisonScale(1.0, 2.0),
            ),
        )

        assert len(painter.texts) == 2
        assert len(painter.bounds) == 2
        assert painter.texts[0] != painter.texts[1]
        assert painter.bounds[0].right() < 400.0
        assert painter.bounds[1].left() > 400.0
    finally:
        canvas.close()
        app.processEvents()


def test_output_grid_preserves_compact_native_tile_packing() -> None:
    """Pack Output grid tiles by their native aspect with compact gutters."""
    app = _app()
    document = OutputCanvasDocument()
    image_ids = tuple(uuid4() for _index in range(3))
    image = QImage(1144, 1608, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    try:
        for image_id in image_ids:
            assert document.admit_image(image_id, image)
        document.workspace.resize(848, 946)
        document.workspace.show()
        assert document.present_grid(image_ids)
        app.processEvents()

        snapshot = document.workspace.gridSnapshot()
        assert snapshot is not None
        assert (snapshot.columns, snapshot.rows) == (2, 2)
        first, second, final = snapshot.frames
        expected_raster_gutter = 2
        expected_scene_gutter = max(2.0, 3216.0 / 511.0)
        stable_scale = min(
            (848.0 - expected_raster_gutter) / (2.0 * 1144.0),
            (946.0 - expected_raster_gutter) / (2.0 * 1608.0),
        )
        assert first.cell.width() == approx(1144.0 * stable_scale, abs=0.1)
        assert first.cell.height() == approx(1608.0 * stable_scale, abs=0.1)
        assert second.cell.x() - first.cell.right() == approx(
            expected_scene_gutter * first.cell.width() / 1144.0,
            abs=0.1,
        )
        assert final.cell.center().x() == snapshot.viewport.center().x()

        first_target = document.workspace.canvasFor(cast(UUID, first.target_id))
        second_target = document.workspace.canvasFor(cast(UUID, second.target_id))
        final_target = document.workspace.canvasFor(cast(UUID, final.target_id))
        assert first_target is not None
        assert second_target is not None
        assert final_target is not None
        first_mount = first_target.parentWidget()
        second_mount = second_target.parentWidget()
        final_mount = final_target.parentWidget()
        assert first_mount is not None
        assert second_mount is not None
        assert final_mount is not None
        for target in (first_target, second_target, final_target):
            assert _wait_for_rendered_color(app, target, QColor("red"))
        assert second_mount.x() - first_mount.x() - first_mount.width() == (
            expected_raster_gutter
        )
        assert final_mount.y() - first_mount.y() - first_mount.height() == (
            expected_raster_gutter
        )
        shared_left = max(first_mount.x(), final_mount.x())
        shared_right = min(
            first_mount.x() + first_mount.width(),
            final_mount.x() + final_mount.width(),
        )
        assert shared_left < shared_right
        _assert_rendered_horizontal_seam(
            document.workspace,
            (shared_left + shared_right) // 2,
            first_mount.y() + first_mount.height(),
            expected_raster_gutter,
        )

        document.workspace.resize(856, 954)
        app.processEvents()
        assert second_mount.x() - first_mount.x() - first_mount.width() == (
            expected_raster_gutter
        )
        assert final_mount.y() - first_mount.y() - first_mount.height() == (
            expected_raster_gutter
        )
        shared_left = max(first_mount.x(), final_mount.x())
        shared_right = min(
            first_mount.x() + first_mount.width(),
            final_mount.x() + final_mount.width(),
        )
        assert shared_left < shared_right
        _assert_rendered_horizontal_seam(
            document.workspace,
            (shared_left + shared_right) // 2,
            first_mount.y() + first_mount.height(),
            expected_raster_gutter,
        )
    finally:
        document.close()
        app.processEvents()


def test_output_grid_preserves_legacy_mixed_source_cells() -> None:
    """Mount each mixed-source image in its old common grid cell."""

    app = _app()
    document = OutputCanvasDocument()
    image_ids = tuple(uuid4() for _index in range(3))
    images = (
        QImage(1144, 1608, QImage.Format.Format_RGB32),
        QImage(1608, 1144, QImage.Format.Format_RGB32),
        QImage(1144, 1608, QImage.Format.Format_RGB32),
    )
    for image, color in zip(images, ("red", "blue", "green"), strict=True):
        image.fill(QColor(color))
    try:
        for image_id, image in zip(image_ids, images, strict=True):
            assert document.admit_image(image_id, image)
        document.workspace.resize(1600, 850)
        document.workspace.show()
        assert document.present_grid(image_ids)
        app.processEvents()

        snapshot = document.workspace.gridSnapshot()
        assert snapshot is not None
        assert (snapshot.columns, snapshot.rows) == (3, 1)
        first, middle, final = snapshot.frames
        assert first.cell == middle.cell.translated(-middle.cell.x(), 0.0)
        assert middle.content.top() > first.content.top()
        assert middle.content.bottom() < first.content.bottom()

        mounts = []
        for frame in snapshot.frames:
            target = document.workspace.canvasFor(cast(UUID, frame.target_id))
            assert target is not None
            mount = target.parentWidget()
            assert mount is not None
            mounts.append(mount)
        assert mounts[0].size() == mounts[1].size() == mounts[2].size()
        assert mounts[1].x() - mounts[0].x() - mounts[0].width() == 2
        assert mounts[2].x() - mounts[1].x() - mounts[1].width() == 2

        document.workspace.resize(1608, 858)
        app.processEvents()
        resized = document.workspace.gridSnapshot()
        assert resized is not None
        resized_mounts = []
        for frame in resized.frames:
            target = document.workspace.canvasFor(cast(UUID, frame.target_id))
            assert target is not None
            mount = target.parentWidget()
            assert mount is not None
            resized_mounts.append(mount)
        assert (
            resized_mounts[0].size()
            == resized_mounts[1].size()
            == resized_mounts[2].size()
        )
        assert (
            resized_mounts[1].x() - resized_mounts[0].x() - resized_mounts[0].width()
            == 2
        )
        assert (
            resized_mounts[2].x() - resized_mounts[1].x() - resized_mounts[1].width()
            == 2
        )
    finally:
        document.close()
        app.processEvents()


def test_output_grid_keeps_fixed_gutters_and_equal_tiles_during_width_resize() -> None:
    """Keep equal Output images aligned through one-pixel width changes."""

    app = _app()
    document = OutputCanvasDocument()
    image_ids = tuple(uuid4() for _index in range(3))
    image = QImage(960, 1344, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    try:
        for image_id in image_ids:
            assert document.admit_image(image_id, image)
        document.workspace.resize(1500, 1000)
        document.workspace.show()
        assert document.present_grid(image_ids)
        app.processEvents()

        composition_ids = tuple(
            document.composition_id_for(image_id) for image_id in image_ids
        )
        assert all(composition_id is not None for composition_id in composition_ids)
        targets = tuple(
            document.workspace.canvasFor(composition_id)
            for composition_id in composition_ids
            if composition_id is not None
        )
        assert all(target is not None for target in targets)
        mounts = tuple(
            target.parentWidget() for target in targets if target is not None
        )
        assert len(mounts) == 3
        assert all(mount is not None for mount in mounts)

        for width in range(1500, 1511):
            document.workspace.resize(width, 1000)
            app.processEvents()
            snapshot = document.workspace.gridSnapshot()
            assert snapshot is not None
            assert (snapshot.columns, snapshot.rows) == (3, 1)
            first, second, final = mounts
            assert first is not None
            assert second is not None
            assert final is not None
            assert first.width() == second.width() == final.width()
            assert first.height() == second.height() == final.height()
            assert second.x() - first.x() - first.width() == 2
            assert final.x() - second.x() - second.width() == 2
    finally:
        document.close()
        app.processEvents()


def test_output_grid_keeps_two_row_targets_relatively_fixed_during_width_resize() -> (
    None
):
    """Keep a centered final-row target fixed relative to its full grid row."""

    app = _app()
    document = OutputCanvasDocument()
    image_ids = tuple(uuid4() for _index in range(3))
    image = QImage(960, 1344, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    try:
        for image_id in image_ids:
            assert document.admit_image(image_id, image)
        document.workspace.resize(920, 1000)
        document.workspace.show()
        assert document.present_grid(image_ids)
        app.processEvents()
        composition_ids = tuple(
            document.composition_id_for(image_id) for image_id in image_ids
        )
        assert all(composition_id is not None for composition_id in composition_ids)
        targets = tuple(
            document.workspace.canvasFor(composition_id)
            for composition_id in composition_ids
            if composition_id is not None
        )
        assert all(target is not None for target in targets)
        mounts = tuple(
            target.parentWidget() for target in targets if target is not None
        )
        assert len(mounts) == 3
        assert all(mount is not None for mount in mounts)

        relative_final_x: int | None = None
        for width in range(920, 931):
            document.workspace.resize(width, 1000)
            app.processEvents()
            snapshot = document.workspace.gridSnapshot()
            assert snapshot is not None
            assert (snapshot.columns, snapshot.rows) == (2, 2)
            first, second, final = mounts
            assert first is not None
            assert second is not None
            assert final is not None
            assert first.size() == second.size() == final.size()
            assert second.x() - first.x() - first.width() == 2
            assert final.y() - first.y() - first.height() == 2
            current_relative_final_x = final.x() - first.x()
            if relative_final_x is None:
                relative_final_x = current_relative_final_x
            assert current_relative_final_x == relative_final_x
    finally:
        document.close()
        app.processEvents()


def test_output_grid_pointer_gesture_starts_transfer_for_its_tile() -> None:
    """Output's installed transfer policy must work from a fitted grid tile."""
    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    provider = _DragProvider()
    try:
        canvas.resize(640, 480)
        canvas.show()
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        canvas.install_transfer_drag_provider(provider)
        assert canvas.document.present_grid((first_id, second_id))
        app.processEvents()
        composition_id = canvas.document.composition_id_for(second_id)
        assert composition_id is not None
        target = canvas.workspace.canvasFor(composition_id)
        assert target is not None
        origin = QPointF(target.rect().center())
        destination = origin + QPointF(20.0, 0.0)

        target.mousePressEvent(
            QMouseEvent(
                QEvent.Type.MouseButtonPress,
                origin,
                origin,
                origin,
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        target.mouseMoveEvent(
            QMouseEvent(
                QEvent.Type.MouseMove,
                destination,
                destination,
                destination,
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )

        assert provider.subjects
        assert getattr(provider.subjects[0], "target_id") == composition_id
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_output_document_replaces_and_retires_content_without_stale_identity() -> None:
    """Replace changed pixels and retire only the corresponding composition."""

    app = _app()
    document = OutputCanvasDocument()
    image_id = uuid4()

    try:
        assert document.admit_image(image_id, _image("red"))
        original_composition = document.composition_id_for(image_id)
        assert original_composition is not None
        reference = document.content_reference_for(image_id)
        assert reference is not None
        assert document.image_id_for_content_reference(reference) == image_id

        assert document.admit_image(image_id, _image("blue"))
        replacement_composition = document.composition_id_for(image_id)
        assert replacement_composition is not None
        assert replacement_composition != original_composition
        assert document.image_id_for_content_reference(reference) is None

        assert document.retire_image(image_id)
        assert document.composition_id_for(image_id) is None
        assert not document.retire_image(image_id)
    finally:
        document.close()
        app.processEvents()


def test_output_document_retains_inactive_workflow_detail_groups() -> None:
    """Keep independent workflow inspection state while another workflow is active."""

    app = _app()
    document = OutputCanvasDocument()
    image_ids = tuple(uuid4() for _index in range(4))
    try:
        for image_id, color in zip(
            image_ids,
            ("red", "blue", "green", "yellow"),
            strict=True,
        ):
            assert document.admit_image(image_id, _image(color))
        first_group_id = uuid4()
        second_group_id = uuid4()
        document.set_detail_inspection_groups(
            workflow_id="first",
            groups=(
                OutputDetailInspectionGroup(
                    first_group_id,
                    "first",
                    "scene",
                    1,
                    image_ids[:2],
                ),
            ),
        )
        document.set_detail_inspection_groups(
            workflow_id="second",
            groups=(
                OutputDetailInspectionGroup(
                    second_group_id,
                    "second",
                    "scene",
                    1,
                    image_ids[2:],
                ),
            ),
        )

        groups = document.workspace.session.inspection.groups()
        assert tuple(group.group_id for group in groups) == (
            first_group_id,
            second_group_id,
        )
        assert set(groups[0].members).isdisjoint(groups[1].members)
    finally:
        document.close()
        app.processEvents()


def test_output_workspace_activation_emits_document_targeted_navigation() -> None:
    """Activate the exact CuteCanvas grid composition without QPane hit testing."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    projection = _projection(first_id, second_id)
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    selected: list[str] = []
    canvas.activeOutputChanged.connect(selected.append)

    try:
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        canvas.bind_projection_session(_session(boundary, projection))
        composition = canvas.document.composition_id_for(second_id)
        assert composition is not None

        canvas._activate_workspace_target(composition)

        assert selected == [str(second_id)]
    finally:
        canvas.close()
        app.processEvents()


def test_output_grid_reselects_target_after_returning_from_detail() -> None:
    """A grid click must navigate even when that image remains session-active."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    selected: list[str] = []
    canvas.activeOutputChanged.connect(selected.append)

    try:
        canvas.resize(900, 600)
        canvas.show()
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        canvas.bind_projection_session(
            _session(boundary, _projection(first_id, second_id))
        )
        canvas.document.present_grid((first_id, second_id))
        app.processEvents()
        composition = canvas.document.composition_id_for(second_id)
        assert composition is not None
        target = canvas.workspace.canvasFor(composition)
        assert target is not None

        QTest.mouseClick(target, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert selected == [str(second_id)]

        canvas.document.present_grid((first_id, second_id))
        app.processEvents()
        returned_target = canvas.workspace.canvasFor(composition)
        assert returned_target is not None
        QTest.mouseClick(returned_target, Qt.MouseButton.LeftButton)
        app.processEvents()

        assert selected == [str(second_id), str(second_id)]
    finally:
        canvas.close()
        app.processEvents()


def test_output_workspace_middle_mouse_divider_updates_compare_state() -> None:
    """Persist a native middle-button divider summon and drag without feedback."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    base = OutputCompareSelection(scene_key=None, source_key="source", set_index=1)
    comparison = OutputCompareSelection(
        scene_key=None,
        source_key="source",
        set_index=2,
    )
    projection = _projection(
        first_id,
        second_id,
        compare_state=OutputCompareState(
            enabled=True,
            base=base,
            comparison=comparison,
            split_position=0.25,
            orientation="vertical",
        ),
    )
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    states: list[OutputCompareState] = []
    canvas.activeOutputCompareChanged.connect(states.append)

    try:
        canvas.resize(900, 600)
        canvas.show()
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        canvas.bind_projection_session(_session(boundary, projection))
        assert states == []
        reprojected: list[OutputCompareState] = []

        def reproject_compare_state(state: OutputCompareState) -> None:
            """Replay persisted compare state through the production projection sink."""

            reprojected.append(state)
            canvas.bind_projection_session(
                _session(
                    boundary,
                    _projection(first_id, second_id, compare_state=state),
                )
            )

        canvas.activeOutputCompareChanged.connect(reproject_compare_state)
        first_composition = canvas.document.composition_id_for(first_id)
        second_composition = canvas.document.composition_id_for(second_id)
        assert first_composition is not None
        assert second_composition is not None

        app.processEvents()
        pane_widget = canvas.workspace.currentCanvas()
        assert pane_widget is not None
        pane = cast(_NativeComparisonProbe, pane_widget)
        called_position = QPoint(
            pane_widget.width() * 2 // 3,
            pane_widget.height() // 2,
        )
        destination = QPoint(
            min(pane_widget.width() - 2, called_position.x() + 80),
            called_position.y(),
        )
        QTest.mousePress(
            pane_widget,
            Qt.MouseButton.MiddleButton,
            pos=called_position,
        )
        app.processEvents()
        called_divider = pane.comparisonDividerState()
        assert called_divider.dragging is True
        assert called_divider.visible_segment is not None
        assert called_divider.visible_segment.x1() == approx(
            called_position.x(),
            abs=1.0,
        )
        QTest.mouseMove(pane_widget, destination)
        QTest.mouseRelease(
            pane_widget,
            Qt.MouseButton.MiddleButton,
            pos=destination,
        )
        app.processEvents()

        indicator = canvas._zoom_indicators._comparison_indicator
        assert indicator.opacity >= 0.0

        assert states[-1].split_position > 0.5
        assert states[-1].orientation == "vertical"
        assert canvas.visible_compare_state == states[-1]
        assert reprojected == states
        assert pane.comparisonDividerState().dragging is False

        canvas.workspace.setComparisonPresentation(
            first_composition,
            second_composition,
            split_position=states[-1].split_position,
            orientation=ComparisonOrientation.HORIZONTAL,
        )
        app.processEvents()
        assert states[-1].split_position == pane.comparisonState().split_position
        assert states[-1].orientation == "horizontal"
        assert canvas.visible_compare_state == states[-1]
        assert reprojected == states
    finally:
        canvas.close()
        app.processEvents()


def test_output_document_preview_admission_preserves_source_and_scene_routes() -> None:
    """Represent accepted live previews as locked document compositions."""

    app = _app()
    final_id = uuid4()
    source_preview_id = uuid4()
    scene_preview_id = uuid4()
    projection = _projection(final_id, uuid4())
    boundary = create_canvas_session_boundary()
    registry = OutputPreviewRegistry()
    canvas = OutputCanvas(
        preview_registry=registry,
        route_session_boundary=boundary,
    )

    try:
        assert canvas.document.admit_image(final_id, _image("red"))
        session = _session(boundary, projection)
        canvas.bind_projection_session(session)
        source_lane = _source_preview_lane(source_preview_id, session)
        registry.store_accepted_lane(source_lane)

        canvas.apply_preview_acceptance(
            OutputPreviewAcceptance(accepted=True, lanes=(source_lane,))
        )

        source_composition = canvas.document.composition_id_for(source_preview_id)
        assert source_composition is not None
        assert canvas.workspace.session.presentation.target_ids == (source_composition,)

        scene_lane = _scene_preview_lane(scene_preview_id, session)
        registry.store_accepted_lane(scene_lane)
        canvas.apply_preview_acceptance(
            OutputPreviewAcceptance(accepted=True, lanes=(scene_lane,))
        )

        scene_composition = canvas.document.composition_id_for(scene_preview_id)
        assert scene_composition is not None
        assert canvas.active_scene_overview is True
        assert scene_composition in canvas.workspace.session.presentation.target_ids
    finally:
        canvas.close()
        app.processEvents()


def test_comfy_preview_event_reaches_the_visible_output_document() -> None:
    """Route an authorized transient Comfy preview into the real active Output view."""

    app = _app()
    final_id = uuid4()
    boundary = create_canvas_session_boundary()
    registry = OutputPreviewRegistry()
    canvas = OutputCanvas(
        preview_registry=registry,
        route_session_boundary=boundary,
    )
    try:
        canvas.resize(640, 480)
        canvas.show()
        assert canvas.document.admit_image(final_id, _image("red"))
        session = _session(boundary, _projection(final_id, uuid4()))
        canvas.bind_projection_session(session)

        first_event = _live_preview_event(_image("green"))
        first_acceptance = registry.accept_preview(
            first_event,
            session=session,
            active_workflow_id="workflow",
            authorize_preview=lambda _identity: True,
        )
        assert first_acceptance.accepted
        canvas.apply_preview_acceptance(first_acceptance)
        preview_id = first_acceptance.lanes[0].preview_id
        first_target_id = canvas.document.composition_id_for(preview_id)
        assert first_target_id is not None
        first_target = canvas.workspace.canvasFor(first_target_id)
        assert first_target is not None
        assert _wait_for_rendered_color(app, first_target, QColor("green"))

        replacement_event = _live_preview_event(_image("blue"))
        replacement_acceptance = registry.accept_preview(
            replacement_event,
            session=session,
            active_workflow_id="workflow",
            authorize_preview=lambda _identity: True,
        )
        assert replacement_acceptance.accepted
        assert replacement_acceptance.lanes[0].preview_id == preview_id
        canvas.apply_preview_acceptance(replacement_acceptance)
        replacement_target_id = canvas.document.composition_id_for(preview_id)
        assert replacement_target_id is not None
        replacement_target = canvas.workspace.canvasFor(replacement_target_id)
        assert replacement_target is not None
        assert _wait_for_rendered_color(app, replacement_target, QColor("blue"))
    finally:
        canvas.close()
        app.processEvents()


def test_output_document_survives_non_destructive_widget_close() -> None:
    """Keep the application-lifetime Output document warm across widget closes."""

    app = _app()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=create_canvas_session_boundary(),
    )
    image_id = uuid4()

    try:
        canvas.close()

        assert canvas.document.admit_image(image_id, _image("purple"))
    finally:
        canvas.deleteLater()
        app.processEvents()


def test_output_canvas_forwards_captured_workspace_context_without_activation() -> None:
    """A content context request should preserve the clicked document reference only."""

    app = _app()
    image_id = uuid4()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    contexts: list[tuple[object, object]] = []
    try:
        assert canvas.document.admit_image(image_id, _image("red"))
        reference = canvas.document.content_reference_for(image_id)
        assert reference is not None
        active_composition_id = canvas.document.session.active_composition_id
        canvas.install_transfer_context_handler(
            lambda subject, position: contexts.append((subject, position))
        )

        canvas.workspace.contentContextRequested.emit(reference, QPoint(12, 20))

        assert contexts == [(reference, QPoint(12, 20))]
        assert canvas.document.session.active_composition_id == active_composition_id
    finally:
        canvas.deleteLater()
        app.processEvents()


def test_output_grid_right_click_forwards_the_clicked_tile_context() -> None:
    """A grid context gesture must address its tile without changing Output route."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=create_canvas_session_boundary(),
    )
    contexts: list[tuple[object, object]] = []
    try:
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        first_reference = canvas.document.content_reference_for(first_id)
        second_reference = canvas.document.content_reference_for(second_id)
        assert first_reference is not None
        assert second_reference is not None
        canvas.document.present_grid((first_id, second_id))
        canvas.install_transfer_context_handler(
            lambda subject, position: contexts.append((subject, position))
        )
        target = canvas.workspace.canvasFor(second_reference.composition_id)
        assert target is not None
        active_before = canvas.document.session.active_composition_id

        app.sendEvent(
            target,
            QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse,
                QPoint(4, 4),
                QPoint(24, 28),
            ),
        )

        assert len(contexts) == 1
        subject, position = contexts[0]
        assert isinstance(subject, DragSubject)
        assert subject.subject_id == second_reference
        assert subject.target_id == second_reference.composition_id
        assert position == QPoint(24, 28)
        assert canvas.document.session.active_composition_id == active_before
    finally:
        canvas.deleteLater()
        app.processEvents()


def test_output_comparison_right_click_forwards_the_established_output_context() -> (
    None
):
    """Native comparison must forward the primary Output content to its normal menu."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=create_canvas_session_boundary(),
    )
    contexts: list[tuple[object, object]] = []
    try:
        canvas.resize(640, 480)
        canvas.show()
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        first_reference = canvas.document.content_reference_for(first_id)
        assert first_reference is not None
        assert canvas.document.present_comparison(
            first_id,
            second_id,
            split_position=0.5,
            orientation="vertical",
        )
        app.processEvents()
        pane = canvas.workspace.currentCanvas()
        assert pane is not None
        canvas.install_transfer_context_handler(
            lambda subject, position: contexts.append((subject, position))
        )

        app.sendEvent(
            pane,
            QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse,
                QPoint(12, 20),
                QPoint(32, 40),
            ),
        )

        assert contexts == [(first_reference, QPoint(32, 40))]
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_composed_output_context_router_connects_to_workspace_signal(
    monkeypatch: MonkeyPatch,
) -> None:
    """Compose the grid Copy route through the real CuteCanvas context signal."""

    app = _app()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=create_canvas_session_boundary(),
    )
    copied: list[object] = []
    rendered_models: list[MenuModel] = []

    class _Menu:
        """Accept the menu execution request without opening a native popup."""

        def exec(self, _position: object, **_kwargs: object) -> None:
            """Record no additional state for this offscreen menu execution."""

    class _Renderer:
        """Capture the model built by the production grid menu."""

        def __init__(self, *, parent: object) -> None:
            """Accept the production renderer constructor contract."""

            del parent

        def render(self, model: MenuModel) -> _Menu:
            """Capture one model instead of creating a native Qt menu."""

            rendered_models.append(model)
            return _Menu()

    monkeypatch.setattr(output_grid_context_menu, "QFluentMenuRenderer", _Renderer)
    image_id = uuid4()
    try:
        assert canvas.document.admit_image(image_id, _image("red"))
        reference = canvas.document.content_reference_for(image_id)
        assert reference is not None
        canvas.document.present_grid((image_id,))

        router = compose_output_context_menu(canvas, request_copy=copied.append)
        canvas.workspace.contentContextRequested.emit(reference, QPoint(24, 28))

        assert router.grid_menu.parent is canvas
        assert len(rendered_models) == 1
        entries = tuple(
            entry for entry in rendered_models[0].entries if isinstance(entry, MenuItem)
        )
        assert tuple(entry.action_id for entry in entries) == (
            "output_canvas.copy",
            "output_canvas.open_current_external",
            "output_canvas.dock_action",
        )
        assert entries[0].callback is not None
        entries[0].callback()
        assert copied == [reference]
    finally:
        canvas.deleteLater()
        app.processEvents()


def test_composed_output_context_router_uses_full_output_actions_for_detail(
    monkeypatch: MonkeyPatch,
) -> None:
    """The production context signal must retain full Output actions in detail mode."""

    app = _app()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    rendered_models: list[MenuModel] = []

    class _Menu:
        """Accept the menu execution request without opening a native popup."""

        def exec(self, _position: object, **_kwargs: object) -> None:
            """Use the same execution contract without native window creation."""

    class _Renderer:
        """Capture one full Output action model from the production renderer."""

        def __init__(self, *, parent: object) -> None:
            """Accept the production renderer constructor contract."""

            del parent

        def render(self, model: MenuModel) -> _Menu:
            """Capture one menu model instead of creating a native popup."""

            rendered_models.append(model)
            return _Menu()

    monkeypatch.setattr(output_canvas_context_menu, "QFluentMenuRenderer", _Renderer)
    first_id = uuid4()
    second_id = uuid4()
    try:
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        canvas.bind_projection_session(
            _session(boundary, _projection(first_id, second_id))
        )
        reference = canvas.document.content_reference_for(first_id)
        assert reference is not None

        router = compose_output_context_menu(
            canvas, request_copy=lambda _reference: None
        )
        canvas.workspace.contentContextRequested.emit(reference, QPoint(24, 28))

        assert router.output_menu.parent is canvas
        assert len(rendered_models) == 1
        entries = tuple(
            entry for entry in rendered_models[0].entries if isinstance(entry, MenuItem)
        )
        assert tuple(entry.action_id for entry in entries) == (
            "output_canvas.compare_outputs",
            "output_canvas.copy",
            "output_canvas.open_current_external",
            "output_canvas.open_all_external",
            "output_canvas.reveal_current_asset",
            "output_canvas.dock_action",
        )
        assert entries[1].icon is FIF.COPY
        assert entries[2].icon is FIF.PHOTO
        assert entries[3].icon is AppIcon.IMAGE_MULTIPLE_20_REGULAR
        assert entries[4].icon is AppIcon.FOLDER_OPEN_20_REGULAR
        assert entries[5].icon is FIF.FULL_SCREEN
    finally:
        canvas.deleteLater()
        app.processEvents()


def _projection(
    first_id: UUID,
    second_id: UUID,
    *,
    compare_state: OutputCompareState = OutputCompareState(),
) -> OutputCanvasProjection:
    """Build one two-image source projection for workspace interaction coverage."""

    first = OutputCanvasImageItem(
        image_id=first_id,
        image_meta=_image_meta(1),
        set_index=1,
    )
    second = OutputCanvasImageItem(
        image_id=second_id,
        image_meta=_image_meta(2),
        set_index=2,
    )
    source = OutputCanvasSourceGroup(
        source_key="source",
        label="Source",
        images_by_set={1: first, 2: second},
    )
    return OutputCanvasProjection(
        sources=(source,),
        active_source_key="source",
        active_set_index=1,
        active_uuid=first.image_id,
        set_count=2,
        compare_state=compare_state,
    )


def _linked_projection(
    first_id: UUID,
    second_id: UUID,
) -> OutputCanvasProjection:
    """Build two source peers in the same unscened batch."""

    first = OutputCanvasImageItem(
        image_id=first_id,
        image_meta=_image_meta(1),
        set_index=1,
    )
    second = OutputCanvasImageItem(
        image_id=second_id,
        image_meta=_image_meta(2),
        set_index=1,
    )
    return OutputCanvasProjection(
        sources=(
            OutputCanvasSourceGroup(
                source_key="first-source",
                label="First source",
                images_by_set={1: first},
            ),
            OutputCanvasSourceGroup(
                source_key="second-source",
                label="Second source",
                images_by_set={1: second},
            ),
        ),
        active_source_key="first-source",
        active_set_index=1,
        active_uuid=first.image_id,
        set_count=1,
    )


def _session(
    boundary: CanvasRouteSessionBoundaryPort,
    projection: OutputCanvasProjection,
) -> OutputCanvasSession:
    """Bind one current Output route session for a test projection."""

    return bind_output_canvas_session(
        boundary,
        workflow_id="workflow",
        projection=projection,
        image_metadata_lookup={
            item.image_id: item.image_meta
            for source in projection.sources
            for item in source.images_by_set.values()
        },
    )


def _image_meta(number: int) -> ImageMeta:
    """Return minimal valid metadata for one generated source image."""

    return ImageMeta(
        workflow_name="workflow",
        cube_name="Source",
        image_number=number,
        suffix="",
        path="",
        source_key="source",
    )


def _source_preview_lane(
    preview_id: UUID,
    session: OutputCanvasSession,
) -> OutputPreviewLane:
    """Return one accepted source-preview lane for the active Output session."""

    return OutputPreviewLane(
        key=OutputPreviewLaneKey.source(
            workflow_id="workflow",
            generation_run_id="run",
            prompt_id="prompt",
            source_key="source",
            scene_key=None,
        ),
        preview_id=preview_id,
        image=_image("green"),
        source_label="Source",
        client_id="client",
        session_revision=session.revision,
    )


def _live_preview_event(image: QImage) -> LivePreviewEvent:
    """Build one strict source preview emitted by the Comfy feedback path."""

    event = LivePreviewEvent.from_update(
        PreviewImageUpdate(
            workflow_id="workflow",
            image=image,
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            node_id="preview-node",
            source_key="source",
            source_label="Source",
        )
    )
    assert event is not None
    return event


def _scene_preview_lane(
    preview_id: UUID,
    session: OutputCanvasSession,
) -> OutputPreviewLane:
    """Return one accepted scene-overview preview lane for the active session."""

    return OutputPreviewLane(
        key=OutputPreviewLaneKey.scene(
            workflow_id="workflow",
            generation_run_id="run",
            prompt_id="prompt",
            scene_run_id="scene-run",
            scene_key="scene",
            source_key="source",
        ),
        preview_id=preview_id,
        image=_image("blue"),
        source_label="Source",
        client_id="client",
        session_revision=session.revision,
        scene_title="Scene",
        scene_order=0,
        scene_count=2,
        accepted_for_overview=True,
    )
