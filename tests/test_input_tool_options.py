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

"""Exercise production contextual Input options through the mounted tool runtime."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import uuid4

from cutecanvas import (
    BrushPreset,
    CuteCanvas,
    EditorIntent,
    EditorTransformTarget,
    RasterExtentPolicy,
)
from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    qInstallMessageHandler,
)
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QImage,
    QMouseEvent,
    QPainter,
    QRegion,
    QWheelEvent,
)
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import (
    QApplication,
    QPushButton,
    QWidget,
)
import pytest
from qfluentwidgets import themeColor  # type: ignore[import-untyped]

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
    create_input_canvas_tool_system,
)
from substitute.presentation.canvas.input.input_canvas_tool_controller import (
    InputCanvasToolController,
)
from substitute.presentation.canvas.input.input_canvas_view import InputCanvas
from substitute.presentation.canvas.input.input_contextual_toolbar_installation import (
    install_input_contextual_toolbar,
)
from substitute.presentation.canvas.input.input_selection_contextual_toolbar import (
    InputSelectionContextualToolbarPage,
)
from substitute.presentation.canvas.input.input_selection_modification_contextual_toolbar import (
    InputSelectionModificationContextualToolbarPage,
)
from substitute.presentation.canvas.input.input_transform_contextual_toolbar import (
    InputTransformContextualToolbarPage,
)
from substitute.presentation.canvas.input.input_tool_options import (
    InputBrushSettingsControl,
    install_input_tool_options,
)
import substitute.presentation.canvas.input.input_canvas_context_menu as input_canvas_context_menu
from tests.support.input_canvas.tool_context_projection import (
    project_authored_input_tool_context,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_GAP,
    CANVAS_CHROME_SURFACE_HEIGHT,
)
from substitute.presentation.canvas.shared.canvas_top_bar import CanvasTopBar
from substitute.presentation.canvas.shared.floating_canvas_surface import (
    floating_canvas_surface_stylesheet,
)
from substitute.presentation.widgets import SpinBox
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from substitute.presentation.resources.fluent_app_icon import AppIcon


def _app() -> QApplication:
    """Return the offscreen application used by production widget tests."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _request_coverage_from_context_menu(
    monkeypatch: pytest.MonkeyPatch,
    canvas: InputCanvas,
) -> MenuModel:
    """Open the mounted canvas menu and invoke its coverage command."""

    rendered_models: list[MenuModel] = []

    class _RenderedMenu:
        """Capture menu execution without starting a nested Qt event loop."""

        def exec(self, *_args: object, **_kwargs: object) -> None:
            """Accept the rendered menu position without blocking the test."""

    class _Renderer:
        """Capture the production model at the renderer boundary."""

        def __init__(self, *, parent: QWidget) -> None:
            """Retain the expected parent for construction parity."""

            self.parent = parent

        def render(self, model: MenuModel) -> _RenderedMenu:
            """Record one model and return a nonblocking menu surface."""

            rendered_models.append(model)
            return _RenderedMenu()

    monkeypatch.setattr(
        input_canvas_context_menu,
        "QFluentMenuRenderer",
        _Renderer,
    )
    canvas.canvas.customContextMenuRequested.emit(QPoint(12, 12))
    _app().processEvents()

    assert len(rendered_models) == 1
    coverage_action = cast(MenuItem, rendered_models[0].entries[0])
    assert coverage_action.action_id == "input_canvas.edit_layer_coverage"
    assert coverage_action.enabled
    assert coverage_action.callback is not None
    coverage_action.callback()
    _app().processEvents()
    return rendered_models[0]


class _LayoutRequestCounter(QObject):
    """Count layout requests delivered to one observed canvas surface."""

    def __init__(self) -> None:
        """Create an empty request counter."""

        super().__init__()
        self.count = 0

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Record layout requests without affecting delivery."""

        del watched
        if event.type() is QEvent.Type.LayoutRequest:
            self.count += 1
        return False


class _MousePressCounter(QObject):
    """Count mouse presses that reach one canvas receiver's local filters."""

    def __init__(self) -> None:
        """Create an empty press counter."""
        super().__init__()
        self.count = 0

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Record local delivery without consuming the pointer event."""
        del watched
        if event.type() is QEvent.Type.MouseButtonPress:
            self.count += 1
        return False


def _drain_events(application: QApplication, *, iterations: int = 24) -> None:
    """Drain enough event-loop turns to expose self-scheduling zero timers."""

    for _iteration in range(iterations):
        application.processEvents()


def _wait_for_spy(spy: QSignalSpy, *, timeout_ms: int = 3000) -> None:
    """Wait for one Qt signal while continuing to process timer-driven UI work."""
    elapsed = 0
    while spy.count() == 0 and elapsed < timeout_ms:
        QTest.qWait(10)
        elapsed += 10
    assert spy.count() > 0


def _wait_for_condition(
    predicate: Callable[[], bool],
    *,
    timeout_ms: int = 3000,
) -> None:
    """Wait for one observable Qt state without assuming queued timing."""
    elapsed = 0
    while not predicate() and elapsed < timeout_ms:
        QTest.qWait(10)
        elapsed += 10
    assert predicate()


def _render_without_children(widget: QWidget) -> QImage:
    """Render one widget's own pixels without overlay child controls."""
    image = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    widget.render(
        painter,
        QPoint(),
        QRegion(),
        QWidget.RenderFlag.DrawWindowBackground,
    )
    painter.end()
    return image


def _mounted_input() -> tuple[InputCanvas, InputCanvasToolController]:
    """Mount production Input document, toolbar, options, and controller."""

    canvas = InputCanvas()
    runtime = create_input_canvas_tool_system()
    install_input_tool_options(runtime, canvas.document.tool_options)
    install_input_contextual_toolbar(runtime, canvas.document.tool_options)
    controller = InputCanvasToolController(
        transform_activator=canvas.document.tool_context.activate_transform,
        operation_setter=canvas.document.set_canvas_operation,
        current_operation_provider=canvas.document.current_canvas_operation,
        runtime=runtime,
    )
    canvas.bind_tool_runtime(
        runtime,
        restore_operation=controller.restore_operation,
    )
    canvas.document.tool_context.changed.connect(
        lambda: project_authored_input_tool_context(
            controller,
            canvas.document.tool_context,
        )
    )
    canvas.document.canvasToolChanged.connect(controller.synchronize_native_tool)
    canvas.toolRequested.connect(controller.request_tool)
    image = QImage(96, 64, QImage.Format.Format_ARGB32)
    image.fill(QColor("black"))
    image_id = uuid4()
    canvas.document.ensure_image_cached(image_id, image, None)
    canvas.document.set_current_image_id(image_id)
    mask_id = canvas.document.create_blank_mask(image_id, QSize(96, 64))
    assert mask_id is not None
    canvas.document.set_active_mask_id(mask_id)
    project_authored_input_tool_context(controller, canvas.document.tool_context)
    canvas.resize(900, 600)
    canvas.show()
    _app().processEvents()
    return canvas, controller


def test_top_bar_cannot_observe_its_own_layout_lifecycle() -> None:
    """Keep self-generated layout requests outside the top-bar input surface."""

    assert "event" not in CanvasTopBar.__dict__


def test_empty_mask_disables_layer_transform_until_content_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mounted Input chrome must follow CuteCanvas meaningful-content state."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, _controller = _mounted_input()
    try:
        transform = canvas.tool_strip.button_for(InputCanvasToolId.TRANSFORM_LAYER)
        assert transform is not None
        assert not canvas.document.tool_context.snapshot.layer_transform_available
        assert not transform.isEnabled()
        assert transform.toolTip() == "Nothing to transform!"

        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        coverage = QImage(96, 64, QImage.Format.Format_Grayscale8)
        coverage.fill(0)
        coverage.setPixelColor(20, 20, QColor(255, 255, 255))
        assert canvas.document.canvas.replaceMaskImage(mask_id, coverage)
        app.processEvents()

        transform = canvas.tool_strip.button_for(InputCanvasToolId.TRANSFORM_LAYER)
        assert canvas.document.tool_context.snapshot.layer_transform_available
        assert transform is not None and transform.isEnabled()
        assert transform.toolTip() == "Transform"

        blank = QImage(96, 64, QImage.Format.Format_Grayscale8)
        blank.fill(0)
        assert canvas.document.canvas.replaceMaskImage(mask_id, blank)
        app.processEvents()
        assert not transform.isEnabled()
        assert transform.toolTip() == "Nothing to transform!"

        assert canvas.document.canvas.undoMaskEdit()
        app.processEvents()
        assert transform.isEnabled()
        assert transform.toolTip() == "Transform"

        assert canvas.document.canvas.redoMaskEdit()
        app.processEvents()
        assert not transform.isEnabled()
        assert transform.toolTip() == "Nothing to transform!"
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_top_bar_reaches_idle_quiescence_after_brush_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canvas chrome must stop scheduling geometry work after one transition."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input()
    requests = _LayoutRequestCounter()
    canvas.canvas_top_bar.installEventFilter(requests)
    geometry_changes: list[None] = []
    canvas.canvas_top_bar.geometryChanged.connect(lambda: geometry_changes.append(None))
    try:
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        _drain_events(app)
        requests.count = 0
        geometry_changes.clear()

        _drain_events(app, iterations=64)

        assert requests.count == 0
        assert geometry_changes == []
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_mask_stroke_never_reflows_stable_canvas_chrome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Brush input must remain isolated from Sugar-owned chrome geometry."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input()
    requests = _LayoutRequestCounter()
    canvas.canvas_top_bar.installEventFilter(requests)
    geometry_changes: list[None] = []
    canvas.canvas_top_bar.geometryChanged.connect(lambda: geometry_changes.append(None))
    try:
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        _drain_events(app)
        start = QPointF(120.0, 240.0)
        finish = QPointF(720.0, 240.0)
        requests.count = 0
        geometry_changes.clear()

        QTest.mousePress(
            canvas.canvas,
            Qt.MouseButton.LeftButton,
            pos=start.toPoint(),
        )
        for step in range(1, 13):
            point = start + (finish - start) * (step / 12.0)
            QTest.mouseMove(canvas.canvas, point.toPoint(), delay=0)
            app.processEvents()
        QTest.mouseRelease(
            canvas.canvas,
            Qt.MouseButton.LeftButton,
            pos=finish.toPoint(),
        )
        _drain_events(app)

        assert requests.count == 0
        assert geometry_changes == []
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_canvas_tool_transitions_settle_without_size_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated options replacement must quiesce without invalid Qt geometry."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input()
    messages: list[str] = []
    previous_handler = qInstallMessageHandler(
        lambda _mode, _context, message: messages.append(message)
    )
    try:
        for _iteration in range(20):
            assert controller.request_tool(InputCanvasToolId.BRUSH)
            app.processEvents()
            assert controller.request_tool(InputCanvasToolId.MASK_RECTANGLE)
            app.processEvents()
        _drain_events(app)

        assert not any("Negative sizes" in message for message in messages)
        assert canvas.canvas_top_bar.isHidden()
        assert canvas.canvas_top_bar.size() == QSize(0, 0)
    finally:
        qInstallMessageHandler(previous_handler)
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_brush_settings_reflow_and_state_follow_one_top_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Brush settings should expand in order and clear with inactive options."""

    app = _app()
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    canvas, controller = _mounted_input()
    try:
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        app.processEvents()
        brush_settings = canvas.tool_options_host.options_control
        assert isinstance(brush_settings, InputBrushSettingsControl)
        assert canvas.canvas_top_bar.parentWidget() is canvas.canvas
        assert canvas.canvas.width() == 900
        assert not brush_settings.expanded
        assert canvas.tool_options_host.height() == CANVAS_CHROME_SURFACE_HEIGHT

        selector_bounds = QRect(8, 8, 84, 36)
        canvas.set_host_chrome_obstacles((selector_bounds,))
        app.processEvents()
        assert canvas.canvas_top_bar.x() == selector_bounds.right() + 9
        assert canvas.canvas_top_bar.y() == selector_bounds.y()
        assert canvas.tool_strip.x() == 8
        assert canvas.tool_strip.y() == selector_bounds.bottom() + 9

        following_control = QWidget(canvas.canvas_top_bar)
        following_control.setFixedSize(24, CANVAS_CHROME_SURFACE_HEIGHT)
        canvas.canvas_top_bar.append_control(following_control)
        following_control.show()
        app.processEvents()
        collapsed_following_x = following_control.x()

        QTest.mouseClick(
            brush_settings.brush_settings.header_button,
            Qt.MouseButton.LeftButton,
        )
        app.processEvents()
        assert brush_settings.expanded
        assert canvas.tool_options_host.height() > CANVAS_CHROME_SURFACE_HEIGHT
        assert following_control.x() > collapsed_following_x
        details = brush_settings.findChild(QWidget, "InputBrushSettingsDetails")
        assert details is not None and details.layout() is not None
        details_margins = details.layout().contentsMargins()
        assert (
            details_margins.left(),
            details_margins.top(),
            details_margins.right(),
            details_margins.bottom(),
        ) == (8, 8, 8, 8)

        QTest.mouseClick(brush_settings.close_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert not brush_settings.expanded
        assert following_control.x() == collapsed_following_x

        canvas.set_host_chrome_obstacles(())
        app.processEvents()
        assert canvas.canvas_top_bar.x() == 8
        assert canvas.tool_strip.x() == 8
        assert canvas.tool_strip.y() == canvas.canvas_top_bar.geometry().bottom() + 9

        assert canvas.tool_strip.styleSheet() == floating_canvas_surface_stylesheet(
            "QFrame#CanvasToolStrip"
        )
        assert (
            canvas.tool_options_host.styleSheet()
            == floating_canvas_surface_stylesheet("QFrame#CanvasToolOptionsHost")
        )

        brush_settings.brush_settings.size_slider.setValue(173)
        brush_settings.brush_settings.hardness_slider.setValue(27)
        brush_settings.brush_settings.opacity_slider.setValue(61)
        app.processEvents()
        preset = canvas.document.tool_options.brush_preset()
        assert preset.size == 173.0
        assert preset.hardness == 0.27
        assert preset.opacity == 0.61
        assert brush_settings.brush_settings.size_value.text() == "173 px"

        assert controller.request_tool(InputCanvasToolId.MASK_RECTANGLE)
        app.processEvents()
        assert canvas.tool_options_host.options_control is None
        assert canvas.tool_options_host.isHidden()
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_brush_settings_preview_tracks_active_layer_color_and_outside_click(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preview color should follow the active mask and outside clicks should pass."""

    app = _app()
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    canvas, controller = _mounted_input()
    outside_button = QPushButton("outside", canvas.canvas)
    outside_button.setGeometry(700, 500, 100, 30)
    outside_button.show()
    outside_clicks: list[bool] = []
    outside_button.clicked.connect(lambda: outside_clicks.append(True))
    try:
        active_mask_id = canvas.document.active_mask_id()
        assert active_mask_id is not None
        layer_color = QColor(231, 45, 137)
        assert canvas.document.set_mask_properties(active_mask_id, color=layer_color)
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        app.processEvents()

        brush_settings = canvas.tool_options_host.options_control
        assert isinstance(brush_settings, InputBrushSettingsControl)
        preview = brush_settings.brush_settings.preview_image()
        assert not preview.isNull()
        center = preview.pixelColor(preview.width() // 2, preview.height() // 2)
        assert (center.red(), center.green(), center.blue()) == (
            layer_color.red(),
            layer_color.green(),
            layer_color.blue(),
        )

        assert controller.request_tool(InputCanvasToolId.ERASER)
        app.processEvents()
        eraser_settings = canvas.tool_options_host.options_control
        assert isinstance(eraser_settings, InputBrushSettingsControl)
        eraser_preview = eraser_settings.brush_settings.preview_image()
        eraser_center = eraser_preview.pixelColor(
            eraser_preview.width() // 2,
            eraser_preview.height() // 2,
        )
        assert eraser_center == QColor(Qt.GlobalColor.white)

        QTest.mouseClick(
            eraser_settings.brush_settings.header_button,
            Qt.MouseButton.LeftButton,
        )
        app.processEvents()
        assert eraser_settings.expanded

        QTest.mouseClick(
            outside_button,
            Qt.MouseButton.LeftButton,
            pos=QPoint(outside_button.width() // 2, outside_button.height() // 2),
        )
        app.processEvents()
        assert not eraser_settings.expanded
        assert outside_clicks == [True]
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_replaced_brush_settings_release_document_subscriptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removed Brush controls must stop observing document state immediately."""
    app = _app()
    canvas, controller = _mounted_input()
    try:
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        _drain_events(app)
        control = canvas.tool_options_host.options_control
        assert isinstance(control, InputBrushSettingsControl)
        assert control.brush_settings.parent() is control

        assert controller.request_tool(InputCanvasToolId.MASK_RECTANGLE)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        _drain_events(app)

        brush_preset_calls: list[None] = []
        brush_preset = canvas.document.tool_options.brush_preset

        def tracked_brush_preset() -> BrushPreset:
            """Record stale option reads while preserving the real result."""
            brush_preset_calls.append(None)
            return brush_preset()

        monkeypatch.setattr(
            canvas.document.tool_options,
            "brush_preset",
            tracked_brush_preset,
        )
        for _iteration in range(24):
            canvas.document.brushPresetChanged.emit()
        _drain_events(app)

        assert brush_preset_calls == []
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_modify_selection_previews_original_and_settles_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contextual modification must replace from its base until Apply or Cancel."""
    app = _app()
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    canvas, controller = _mounted_input()
    try:
        assert canvas.contextual_toolbar.page is None
        assert not canvas.contextual_toolbar.isVisible()
        selection = QImage(20, 16, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(20, 18, 20, 16),
        )
        app.processEvents()

        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        assert page.modify_button.text() == "Modify selection"
        QTest.mouseClick(page.modify_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        modification_page = canvas.contextual_toolbar.page
        assert isinstance(
            modification_page,
            InputSelectionModificationContextualToolbarPage,
        )
        _wait_for_condition(modification_page.isVisible)
        controls = modification_page.controls
        assert [
            controls.operation_selector.itemText(index)
            for index in range(controls.operation_selector.count())
        ] == ["Expand", "Contract", "Feather"]
        assert isinstance(controls.pixel_amount, SpinBox)
        assert not controls.pixel_amount.isSymbolVisible()
        assert controls.pixel_amount.maximum() == 999
        assert controls.pixel_amount.width() == 42
        assert controls.pixel_amount.height() == CANVAS_CHROME_CONTROL_HEIGHT
        assert controls.operation_selector.height() == CANVAS_CHROME_CONTROL_HEIGHT
        assert controls.pixel_amount.alignment() == Qt.AlignmentFlag.AlignCenter
        assert modification_page.layout().count() == 2
        assert modification_page.cancel_button.toolTip() == "Cancel"
        assert modification_page.apply_button.toolTip() == "Apply"
        assert modification_page.cancel_button.accessibleName() == "Cancel"
        assert modification_page.apply_button.accessibleName() == "Apply"
        assert modification_page.cancel_button.size() == QSize(
            CANVAS_CHROME_CONTROL_HEIGHT,
            CANVAS_CHROME_CONTROL_HEIGHT,
        )
        assert modification_page.apply_button.size() == QSize(
            CANVAS_CHROME_CONTROL_HEIGHT,
            CANVAS_CHROME_CONTROL_HEIGHT,
        )
        assert modification_page.apply_button.x() < modification_page.cancel_button.x()
        settlement_left = modification_page.settlement_controls.mapTo(
            modification_page,
            modification_page.apply_button.pos(),
        ).x()
        assert (
            settlement_left - modification_page.controls.geometry().right() - 1
            >= CANVAS_CHROME_GAP
        )
        assert modification_page.cancel_button.y() == modification_page.apply_button.y()
        _wait_for_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(16, 14, 28, 24)
            )
        )

        controls.operation_selector.setCurrentIndex(1)
        controls.pixel_amount.setValue(2)
        _wait_for_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(22, 20, 16, 12)
            )
        )
        wheel_position = controls.pixel_amount.rect().center()
        wheel_event = QWheelEvent(
            QPointF(wheel_position),
            QPointF(controls.pixel_amount.mapToGlobal(wheel_position)),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(controls.pixel_amount, wheel_event)
        assert wheel_event.isAccepted()
        assert controls.pixel_amount.value() == 3
        _wait_for_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(23, 21, 14, 10)
            )
        )
        controls.pixel_amount.setValue(2)
        _wait_for_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(22, 20, 16, 12)
            )
        )

        QTest.mouseClick(modification_page.cancel_button, Qt.MouseButton.LeftButton)
        _wait_for_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(20, 18, 20, 16)
            )
        )
        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        _wait_for_condition(page.isVisible)

        QTest.mouseClick(page.modify_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        modification_page = canvas.contextual_toolbar.page
        assert isinstance(
            modification_page,
            InputSelectionModificationContextualToolbarPage,
        )
        _wait_for_condition(modification_page.isVisible)
        completed = QSignalSpy(
            canvas.document.canvas.pixelSelectionModificationCompleted
        )
        modification_page.controls.pixel_amount.setValue(5)
        QTest.mouseClick(modification_page.apply_button, Qt.MouseButton.LeftButton)
        _wait_for_spy(completed)
        _wait_for_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(15, 13, 30, 26)
            )
        )
        assert isinstance(
            canvas.contextual_toolbar.page,
            InputSelectionContextualToolbarPage,
        )
        assert canvas.document.canvas.undoSceneEdit()
        _wait_for_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(20, 18, 20, 16)
            )
        )
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_contextual_toolbar_drags_clamps_and_deselects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selection chrome must retain movable placement and derive dismissal from state."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, _controller = _mounted_input()
    try:
        selection = QImage(12, 12, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(34, 22, 12, 12),
        )
        app.processEvents()

        toolbar = canvas.contextual_toolbar
        page = toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        assert toolbar.drag_handle.cursor().shape() is Qt.CursorShape.ArrowCursor
        assert toolbar.drag_handle.width() < toolbar.drag_handle.height()
        assert toolbar.drag_handle.x() < toolbar.content_host.x()
        pill_image = toolbar.drag_handle.grab().toImage()
        painted_accent = pill_image.pixelColor(pill_image.rect().center())
        expected_accent = QColor(themeColor())
        assert painted_accent.name() == expected_accent.name()
        panel_selection = canvas.document.tool_options.pixel_selection_panel_bounds()
        assert panel_selection is not None
        assert toolbar.geometry().top() > panel_selection.bottom()
        start = toolbar.pos()
        toolbar.drag_handle.dragged.emit(QPoint(30, -70))
        app.processEvents()
        assert toolbar.pos() == start + QPoint(30, -70)

        retained_center = toolbar.geometry().center()
        QTest.mouseClick(page.modify_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert (toolbar.geometry().center() - retained_center).manhattanLength() <= 1
        modification_page = toolbar.page
        assert isinstance(
            modification_page,
            InputSelectionModificationContextualToolbarPage,
        )
        _wait_for_condition(modification_page.isVisible)
        QTest.mouseClick(modification_page.cancel_button, Qt.MouseButton.LeftButton)
        _wait_for_condition(
            lambda: (
                isinstance(
                    toolbar.page,
                    InputSelectionContextualToolbarPage,
                )
                and bool(toolbar.page is not None and toolbar.page.isVisible())
            )
        )

        toolbar.drag_handle.dragged.emit(QPoint(10_000, 10_000))
        app.processEvents()
        assert canvas.canvas.rect().contains(toolbar.geometry())

        current_page = toolbar.page
        assert isinstance(current_page, InputSelectionContextualToolbarPage)
        deselect = current_page.action_strip.button_for(InputCanvasToolId.DESELECT)
        assert deselect is not None
        deselect_widget = cast(QWidget, deselect)
        _wait_for_condition(deselect_widget.isEnabled)
        deselect_widget.setFocus(Qt.FocusReason.MouseFocusReason)
        assert QApplication.focusWidget() is deselect_widget
        QTest.mouseClick(deselect_widget, Qt.MouseButton.LeftButton)
        app.processEvents()
        cleared_selection = canvas.document.canvas.pixelSelectionState()
        assert cleared_selection is not None and not cleared_selection.has_selection
        _wait_for_condition(lambda: toolbar.page is None)
        _wait_for_condition(lambda: not toolbar.isVisible())
        assert QApplication.focusWidget() is canvas.document.canvas
        QTest.keyPress(canvas.document.canvas, Qt.Key.Key_Space)
        assert (
            canvas.document.canvas.getControlMode() == CuteCanvas.CONTROL_MODE_PANZOOM
        )
        assert not canvas.window().isMinimized()
        QTest.keyRelease(canvas.document.canvas, Qt.Key.Key_Space)
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_contextual_toolbar_clear_erases_selected_mask_pixels_without_deselecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clear must edit the active layer while retaining selection context."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input()
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        mask_pixels = QImage(96, 64, QImage.Format.Format_Grayscale8)
        mask_pixels.fill(0)
        mask_painter = QPainter(mask_pixels)
        mask_painter.fillRect(QRect(34, 22, 12, 12), QColor(255, 255, 255))
        mask_painter.end()
        assert canvas.document.canvas.replaceMaskImage(mask_id, mask_pixels)
        mask_info = canvas.document.canvas.listMasksForComposition()[0]
        assert mask_info.scene_id is not None
        assert mask_info.layer_id is not None
        canvas.document.canvas.setRasterExtentPolicy(
            mask_info.scene_id,
            mask_info.layer_id,
            RasterExtentPolicy.EXPAND_ON_WRITE,
        )
        compacting_selection = QImage(12, 12, QImage.Format.Format_Grayscale8)
        compacting_selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            compacting_selection,
            QRect(34, 22, 12, 12),
        )
        assert canvas.document.canvas.deleteSelectedPixels()
        assert canvas.document.canvas.undoSceneEdit()
        selection = QImage(40, 32, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(24, 12, 40, 32),
        )
        project_authored_input_tool_context(controller, canvas.document.tool_context)
        app.processEvents()
        before = canvas.document.export_mask_image(mask_id)
        assert before is not None
        assert before.pixelColor(36, 24).red() == 255
        assert canvas.document.tool_context.snapshot.selection_clear_available
        content_changes = QSignalSpy(canvas.document.maskContentChanged)
        assert canvas.document.tool_options.clear_selected_pixels()
        app.processEvents()
        assert content_changes.count() == 1
        assert canvas.document.canvas.undoSceneEdit()
        app.processEvents()
        assert content_changes.count() == 2
        restored = canvas.document.export_mask_image(mask_id)
        assert restored is not None
        assert restored.pixelColor(36, 24).red() == 255

        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        clear = page.action_strip.button_for(InputCanvasToolId.CLEAR_SELECTION_PIXELS)
        assert clear is not None
        clear_presentation = controller.palette.presentation_for(
            InputCanvasToolId.CLEAR_SELECTION_PIXELS
        )
        assert clear_presentation is not None
        assert clear_presentation.icon is AppIcon.ERASER_20_REGULAR
        _wait_for_condition(clear.isEnabled)
        requested = QSignalSpy(canvas.toolRequested)
        QTest.mouseClick(clear, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert requested.count() == 1
        assert requested.at(0)[0] == InputCanvasToolId.CLEAR_SELECTION_PIXELS
        assert content_changes.count() == 3

        after = canvas.document.export_mask_image(mask_id)
        assert after is not None
        assert after.pixelColor(36, 24).red() == 0
        assert canvas.document.tool_context.snapshot.has_pixel_selection
        assert canvas.contextual_toolbar.isVisible()
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_delete_key_clears_selection_pixels_from_any_active_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delete should follow selection state instead of the current tool mode."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input()
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        mask_pixels = QImage(96, 64, QImage.Format.Format_Grayscale8)
        mask_pixels.fill(255)
        assert canvas.document.canvas.replaceMaskImage(mask_id, mask_pixels)
        selection = QImage(12, 12, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(34, 22, 12, 12),
        )
        app.processEvents()
        content_changes = QSignalSpy(canvas.document.maskContentChanged)

        assert controller.request_tool(InputCanvasToolId.SELECT_RECTANGLE)
        QTest.keyClick(canvas.document.canvas, Qt.Key.Key_Delete)
        app.processEvents()

        cleared = canvas.document.export_mask_image(mask_id)
        assert cleared is not None
        assert cleared.pixelColor(36, 24).red() == 0
        assert content_changes.count() == 1
        assert canvas.document.tool_context.snapshot.has_pixel_selection

        assert canvas.document.canvas.undoSceneEdit()
        app.processEvents()
        assert content_changes.count() == 2
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        QTest.keyClick(canvas.document.canvas, Qt.Key.Key_Delete)
        app.processEvents()

        cleared_from_brush = canvas.document.export_mask_image(mask_id)
        assert cleared_from_brush is not None
        assert cleared_from_brush.pixelColor(36, 24).red() == 0
        assert content_changes.count() == 3
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_contextual_toolbar_hides_during_selection_authoring_and_follows_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selection gestures must hide chrome and remount it below updated bounds."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input()
    try:
        selection = QImage(12, 12, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(34, 22, 12, 12),
        )
        app.processEvents()
        toolbar = canvas.contextual_toolbar
        assert toolbar.isVisible()
        old_panel_bounds = canvas.document.tool_options.pixel_selection_panel_bounds()
        assert old_panel_bounds is not None

        assert controller.request_tool(InputCanvasToolId.SELECT_RECTANGLE)
        gesture = canvas.document.canvas.sceneToPanelRect(QRectF(6, 6, 18, 14))
        assert gesture is not None
        QTest.mousePress(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=gesture.topLeft().toPoint(),
        )
        app.processEvents()
        _wait_for_condition(lambda: not toolbar.isVisible())
        QTest.mouseMove(canvas.document.canvas, gesture.bottomRight().toPoint())
        QTest.mouseRelease(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=gesture.bottomRight().toPoint(),
        )
        _wait_for_condition(toolbar.isVisible)

        new_panel_bounds = canvas.document.tool_options.pixel_selection_panel_bounds()
        assert new_panel_bounds is not None
        assert new_panel_bounds != old_panel_bounds
        assert toolbar.geometry().top() > new_panel_bounds.bottom()
        assert toolbar.geometry().contains(
            QPoint(new_panel_bounds.center().x(), toolbar.geometry().top())
        )

        previous_panel_bounds = QRect(new_panel_bounds)
        canvas.document.canvas.applyZoom(
            canvas.document.canvas.currentZoom() * 1.15,
            canvas.document.canvas.rect().center(),
        )
        app.processEvents()
        zoomed_panel_bounds = (
            canvas.document.tool_options.pixel_selection_panel_bounds()
        )
        assert zoomed_panel_bounds is not None
        assert zoomed_panel_bounds != previous_panel_bounds
        assert toolbar.geometry().top() > zoomed_panel_bounds.bottom()

        pan_start = canvas.document.canvas.rect().center()
        pan_end = pan_start + QPoint(48, 24)
        QTest.keyPress(canvas.document.canvas, Qt.Key.Key_Space)
        QTest.mousePress(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=pan_start,
        )
        QTest.mouseMove(canvas.document.canvas, pan_end)
        QTest.mouseRelease(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=pan_end,
        )
        QTest.keyRelease(canvas.document.canvas, Qt.Key.Key_Space)
        app.processEvents()

        panned_panel_bounds = (
            canvas.document.tool_options.pixel_selection_panel_bounds()
        )
        assert panned_panel_bounds is not None
        assert panned_panel_bounds != zoomed_panel_bounds
        assert toolbar.geometry().top() > panned_panel_bounds.bottom()
        assert toolbar.geometry().contains(
            QPoint(panned_panel_bounds.center().x(), toolbar.geometry().top())
        )
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_contextual_transform_requires_explicit_apply_or_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selected-pixel transform must morph chrome and settle through one explicit path."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input()
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        coverage = QImage(96, 64, QImage.Format.Format_Grayscale8)
        coverage.fill(0)
        for y in range(22, 34):
            for x in range(34, 46):
                coverage.setPixelColor(x, y, QColor(255, 255, 255))
        assert canvas.document.canvas.replaceMaskImage(mask_id, coverage)
        before = canvas.document.export_mask_image(mask_id)
        assert before is not None
        selection = QImage(12, 12, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(34, 22, 12, 12),
        )
        project_authored_input_tool_context(controller, canvas.document.tool_context)
        app.processEvents()

        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        _wait_for_condition(page.isVisible)
        transform = page.action_strip.button_for(InputCanvasToolId.TRANSFORM_SELECTION)
        assert transform is not None and transform.isEnabled()
        QTest.mouseClick(transform, Qt.MouseButton.LeftButton)
        app.processEvents()
        transaction = canvas.contextual_toolbar.page
        assert isinstance(transaction, InputTransformContextualToolbarPage)
        _wait_for_condition(transaction.isVisible)
        assert transaction.apply_button.toolTip() == "Apply"
        assert transaction.cancel_button.toolTip() == "Cancel"
        assert transaction.apply_button.x() < transaction.cancel_button.x()
        settlement_left = transaction.settlement_controls.mapTo(
            transaction,
            transaction.apply_button.pos(),
        ).x()
        assert (
            settlement_left - transaction.flip_vertical_button.geometry().right() - 1
            >= CANVAS_CHROME_GAP
        )
        assert (
            canvas.document.current_canvas_operation()
            == CuteCanvas.CONTROL_MODE_TRANSFORM
        )
        assert not canvas.tool_strip.isVisible()
        assert not canvas.canvas_top_bar.isVisible()
        assert not transaction.history_controls.undo_button.isEnabled()
        assert transaction.cancel_button.isEnabled()

        cancelled_without_history = QSignalSpy(transaction.cancelRequested)
        QTest.mouseClick(transaction.cancel_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert cancelled_without_history.count() == 1
        assert canvas.edit_sessions.snapshot is None
        assert canvas.document.canvas.floatingPixelEditState() is None
        assert canvas.document.export_mask_image(mask_id) == before
        assert (
            canvas.document.current_canvas_operation()
            != CuteCanvas.CONTROL_MODE_TRANSFORM
        )

        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        _wait_for_condition(page.isVisible)
        transform = page.action_strip.button_for(InputCanvasToolId.TRANSFORM_SELECTION)
        assert transform is not None and transform.isEnabled()
        QTest.mouseClick(transform, Qt.MouseButton.LeftButton)
        app.processEvents()
        transaction = canvas.contextual_toolbar.page
        assert isinstance(transaction, InputTransformContextualToolbarPage)
        _wait_for_condition(transaction.isVisible)

        start_rect = canvas.document.canvas.sceneToPanelRect(
            QRectF(40.0, 28.0, 1.0, 1.0)
        )
        end_rect = canvas.document.canvas.sceneToPanelRect(QRectF(52.0, 28.0, 1.0, 1.0))
        assert start_rect is not None and end_rect is not None
        start = start_rect.topLeft()
        end = end_rect.topLeft()
        QTest.mousePress(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=start.toPoint(),
        )
        _wait_for_condition(lambda: not canvas.contextual_toolbar.isVisible())
        QTest.mouseMove(canvas.document.canvas, end.toPoint())
        QTest.mouseRelease(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=end.toPoint(),
        )
        _wait_for_condition(canvas.contextual_toolbar.isVisible)
        assert canvas.document.canvas.floatingPixelEditState() is not None
        transform_bounds = canvas.document.tool_options.transform_panel_bounds(
            EditorTransformTarget.SELECTION_CONTENT
        )
        assert transform_bounds is not None
        assert canvas.contextual_toolbar.geometry().top() > transform_bounds.bottom()
        assert canvas.document.export_mask_image(mask_id) == before
        assert canvas.edit_sessions.snapshot is not None
        assert canvas.edit_sessions.snapshot.can_cancel
        transaction = canvas.contextual_toolbar.page
        assert isinstance(transaction, InputTransformContextualToolbarPage)

        cancelled = QSignalSpy(transaction.cancelRequested)
        QTest.mouseClick(transaction.cancel_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert cancelled.count() == 1
        assert canvas.edit_sessions.snapshot is None
        assert canvas.document.canvas.floatingPixelEditState() is None
        assert canvas.document.export_mask_image(mask_id) == before
        assert (
            canvas.document.current_canvas_operation()
            != CuteCanvas.CONTROL_MODE_TRANSFORM
        )
        assert isinstance(
            canvas.contextual_toolbar.page,
            InputSelectionContextualToolbarPage,
        )

        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        _wait_for_condition(page.isVisible)
        transform = page.action_strip.button_for(InputCanvasToolId.TRANSFORM_SELECTION)
        assert transform is not None
        QTest.mouseClick(transform, Qt.MouseButton.LeftButton)
        app.processEvents()
        transaction = canvas.contextual_toolbar.page
        assert isinstance(transaction, InputTransformContextualToolbarPage)
        _wait_for_condition(transaction.isVisible)
        QTest.mousePress(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=start.toPoint(),
        )
        QTest.mouseMove(canvas.document.canvas, end.toPoint())
        QTest.mouseRelease(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=end.toPoint(),
        )
        app.processEvents()
        assert canvas.document.canvas.floatingPixelEditState() is not None

        QTest.mouseClick(transaction.apply_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        after = canvas.document.export_mask_image(mask_id)
        assert after is not None and after != before
        assert canvas.document.canvas.floatingPixelEditState() is None
        assert canvas.document.canvas.undoSceneEdit()
        assert canvas.document.export_mask_image(mask_id) == before
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_move_drag_hides_then_reanchors_aligned_toolbar_to_floating_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selected-pixel movement must hide chrome and settle against its final frame."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input()
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        coverage = QImage(96, 64, QImage.Format.Format_Grayscale8)
        coverage.fill(0)
        for y in range(8, 20):
            for x in range(14, 30):
                coverage.setPixelColor(x, y, QColor(255, 255, 255))
        assert canvas.document.canvas.replaceMaskImage(mask_id, coverage)
        selection = QImage(16, 12, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(14, 8, 16, 12),
        )
        project_authored_input_tool_context(controller, canvas.document.tool_context)
        assert controller.request_tool(InputCanvasToolId.MOVE)
        app.processEvents()
        assert isinstance(
            canvas.contextual_toolbar.page,
            InputSelectionContextualToolbarPage,
        )

        start_rect = canvas.document.canvas.sceneToPanelRect(
            QRectF(20.0, 14.0, 1.0, 1.0)
        )
        end_rect = canvas.document.canvas.sceneToPanelRect(QRectF(34.0, 20.0, 1.0, 1.0))
        assert start_rect is not None and end_rect is not None
        QTest.mousePress(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=start_rect.topLeft().toPoint(),
        )
        _wait_for_condition(lambda: not canvas.contextual_toolbar.isVisible())
        QTest.mouseMove(canvas.document.canvas, end_rect.topLeft().toPoint())
        QTest.mouseRelease(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=end_rect.topLeft().toPoint(),
        )
        _wait_for_condition(canvas.contextual_toolbar.isVisible)

        floating = canvas.document.canvas.floatingPixelEditState()
        assert floating is not None and not floating.dragging
        floating_bounds = canvas.document.tool_options.floating_pixel_panel_bounds(
            floating
        )
        assert floating_bounds is not None
        assert canvas.contextual_toolbar.geometry().top() > floating_bounds.bottom()
        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        assert page.geometry() == canvas.contextual_toolbar.content_host.rect()
        assert page.modify_button.y() == 0
        assert page.action_strip.y() == 0
        assert page.modify_button.height() == page.action_strip.height()
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_layer_transform_uses_tight_content_frame_and_contextual_settlement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route toolbar layer transforms through the shared live-frame surface."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input()
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        coverage = QImage(96, 64, QImage.Format.Format_Grayscale8)
        coverage.fill(0)
        for y in range(8, 20):
            for x in range(14, 30):
                coverage.setPixelColor(x, y, QColor(255, 255, 255))
        assert canvas.document.canvas.replaceMaskImage(mask_id, coverage)
        before = canvas.document.export_mask_image(mask_id)
        assert before is not None
        assert not canvas.document.tool_context.snapshot.has_pixel_selection

        project_authored_input_tool_context(controller, canvas.document.tool_context)
        presentation = controller.palette.presentation_for(
            InputCanvasToolId.TRANSFORM_LAYER
        )
        assert presentation is not None and presentation.enabled
        initial_state = canvas.document.canvas.editorTransformState(
            EditorTransformTarget.LAYER_CONTENT
        )
        assert initial_state.allowed, initial_state.denial
        assert controller.request_tool(InputCanvasToolId.TRANSFORM_LAYER)
        app.processEvents()

        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputTransformContextualToolbarPage)
        state = canvas.document.canvas.editorTransformState(
            EditorTransformTarget.LAYER_CONTENT
        )
        assert state.allowed and state.corners is not None
        assert canvas.edit_sessions.snapshot is None
        assert not page.history_controls.undo_button.isEnabled()
        assert not page.history_controls.redo_button.isEnabled()
        assert not page.apply_button.isEnabled()
        assert page.cancel_button.isEnabled()

        cancelled_without_history = QSignalSpy(page.cancelRequested)
        QTest.mouseClick(page.cancel_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert cancelled_without_history.count() == 1
        assert canvas.edit_sessions.snapshot is None
        assert (
            canvas.document.current_canvas_operation()
            != CuteCanvas.CONTROL_MODE_TRANSFORM
        )
        _wait_for_condition(lambda: canvas.contextual_toolbar.page is None)

        assert controller.request_tool(InputCanvasToolId.TRANSFORM_LAYER)
        app.processEvents()
        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputTransformContextualToolbarPage)
        panel_bounds = canvas.document.tool_options.transform_panel_bounds(
            EditorTransformTarget.LAYER_CONTENT
        )
        assert panel_bounds is not None
        assert canvas.contextual_toolbar.geometry().top() > panel_bounds.bottom()
        assert not canvas.tool_strip.isVisible()
        assert not canvas.canvas_top_bar.isVisible()

        QTest.mouseClick(page.rotate_right_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert canvas.document.export_mask_image(mask_id) == before
        assert canvas.edit_sessions.snapshot is not None
        assert canvas.edit_sessions.snapshot.can_cancel
        assert page is canvas.contextual_toolbar.page
        assert page.history_controls.undo_button.isEnabled()
        assert not page.history_controls.redo_button.isEnabled()

        QTest.mouseClick(
            page.history_controls.undo_button,
            Qt.MouseButton.LeftButton,
        )
        app.processEvents()
        assert canvas.edit_sessions.snapshot is not None
        assert canvas.edit_sessions.snapshot.undo_depth == 0
        assert canvas.edit_sessions.snapshot.redo_depth == 1
        assert not page.history_controls.undo_button.isEnabled()
        assert page.history_controls.redo_button.isEnabled()
        assert canvas.document.export_mask_image(mask_id) == before

        QTest.mouseClick(
            page.history_controls.redo_button,
            Qt.MouseButton.LeftButton,
        )
        app.processEvents()
        assert canvas.edit_sessions.snapshot is not None
        assert canvas.edit_sessions.snapshot.undo_depth == 1
        assert canvas.edit_sessions.snapshot.redo_depth == 0
        assert page.history_controls.undo_button.isEnabled()
        assert not page.history_controls.redo_button.isEnabled()

        cancelled = QSignalSpy(page.cancelRequested)
        QTest.mouseClick(page.cancel_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert cancelled.count() == 1
        assert canvas.edit_sessions.snapshot is None
        assert canvas.document.export_mask_image(mask_id) == before
        assert (
            canvas.document.current_canvas_operation()
            != CuteCanvas.CONTROL_MODE_TRANSFORM
        )
        _wait_for_condition(lambda: canvas.contextual_toolbar.page is None)
        assert canvas.contextual_toolbar.page is None
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_contextual_transform_rejects_selection_without_active_mask_pixels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never advertise a selection transform that would target the whole mask."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input()
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        coverage = QImage(96, 64, QImage.Format.Format_Grayscale8)
        coverage.fill(0)
        for y in range(6, 18):
            for x in range(6, 18):
                coverage.setPixelColor(x, y, QColor(255, 255, 255))
        assert canvas.document.canvas.replaceMaskImage(mask_id, coverage)
        selection = QImage(12, 12, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(68, 40, 12, 12),
        )

        project_authored_input_tool_context(controller, canvas.document.tool_context)
        app.processEvents()

        assert not canvas.document.tool_context.snapshot.selection_transform_available
        state = canvas.document.canvas.editorOperationState(EditorIntent.TRANSFORM)
        assert not state.allowed
        assert state.denial == "no-selected-pixels"
        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        transform = page.action_strip.button_for(InputCanvasToolId.TRANSFORM_SELECTION)
        assert transform is not None and not transform.isEnabled()
        previous_operation = canvas.document.current_canvas_operation()
        assert not controller.request_tool(InputCanvasToolId.TRANSFORM_SELECTION)
        assert canvas.document.current_canvas_operation() == previous_operation
        assert isinstance(
            canvas.contextual_toolbar.page,
            InputSelectionContextualToolbarPage,
        )
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_real_selection_tools_use_selection_modes_without_mask_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rectangle, ellipse, and lasso selection tools must be first-class modes."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input()
    try:
        for tool_id in (
            InputCanvasToolId.SELECT_RECTANGLE,
            InputCanvasToolId.SELECT_ELLIPSE,
            InputCanvasToolId.SELECT_LASSO,
        ):
            presentation = controller.palette.presentation_for(tool_id)
            assert presentation is not None and presentation.enabled
            assert controller.request_tool(tool_id)
            app.processEvents()
            assert controller.palette.active_tool_id == tool_id
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_layer_coverage_editor_previews_exclusively_and_commits_only_on_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer coverage must use one exclusive preview with explicit settlement."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, _controller = _mounted_input()
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        coverage = QImage(96, 64, QImage.Format.Format_Grayscale8)
        coverage.fill(0)
        for y in range(24, 40):
            for x in range(40, 56):
                coverage.setPixelColor(x, y, QColor(255, 255, 255))
        assert canvas.document.canvas.replaceMaskImage(mask_id, coverage)
        before = canvas.document.export_mask_image(mask_id)
        assert before is not None
        canvas.document.canvas.setCursor(Qt.CursorShape.CrossCursor)
        completed = QSignalSpy(canvas.document.canvas.layerEdgeModificationCompleted)
        rendered_before = _render_without_children(canvas.document.canvas)
        press_counter = _MousePressCounter()
        canvas.document.canvas.installEventFilter(press_counter)
        menu_model = _request_coverage_from_context_menu(monkeypatch, canvas)
        assert all(
            not entry.action_id.startswith("canvas.tool.")
            for entry in menu_model.entries
            if isinstance(entry, MenuItem)
        )

        editor = canvas.coverage_editor
        assert canvas.coverage_edit_active
        assert editor.isVisible()
        assert not canvas.tool_strip.isVisible()
        assert not canvas.canvas_top_bar.isVisible()
        assert (
            abs(editor.geometry().center().x() - canvas.canvas.rect().center().x()) <= 1
        )
        assert editor.geometry().bottom() == canvas.canvas.height() - 9
        assert editor.controls.operation_selector.itemText(0) == "Expand"
        assert editor.controls.operation_selector.itemText(1) == "Contract"
        assert editor.controls.operation_selector.itemText(2) == "Feather"
        assert editor.controls.pixel_amount.value() == 4

        context_menu_requests = QSignalSpy(
            canvas.document.canvas.customContextMenuRequested
        )
        blocked_context_menu = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            QPoint(20, 20),
            canvas.document.canvas.mapToGlobal(QPoint(20, 20)),
        )
        QApplication.sendEvent(canvas.document.canvas, blocked_context_menu)
        assert blocked_context_menu.isAccepted()
        assert context_menu_requests.count() == 0

        blocked_press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(20.0, 20.0),
            QPointF(canvas.document.canvas.mapToGlobal(QPoint(20, 20))),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(canvas.document.canvas, blocked_press)
        assert press_counter.count == 0

        editor.controls.pixel_amount.setValue(2)
        _wait_for_condition(
            lambda: _render_without_children(canvas.document.canvas) != rendered_before
        )
        assert completed.count() == 0
        assert canvas.document.export_mask_image(mask_id) == before

        QTest.mouseClick(editor.apply_button, Qt.MouseButton.LeftButton)
        _wait_for_spy(completed)
        app.processEvents()
        after = canvas.document.export_mask_image(mask_id)
        assert after is not None and after != before
        assert not canvas.coverage_edit_active
        assert not editor.isVisible()
        assert canvas.tool_strip.isVisible()
        assert canvas.document.canvas.undoMaskEdit()
        assert canvas.document.export_mask_image(mask_id) == before

        _request_coverage_from_context_menu(monkeypatch, canvas)
        assert canvas.coverage_edit_active
        editor.controls.pixel_amount.setValue(3)
        QTest.mouseClick(editor.close_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert not canvas.coverage_edit_active
        assert canvas.document.export_mask_image(mask_id) == before

        _request_coverage_from_context_menu(monkeypatch, canvas)
        assert canvas.coverage_edit_active
        editor.controls.pixel_amount.setValue(2)
        canvas.close()
        app.processEvents()
        assert not canvas.coverage_edit_active
        assert canvas.document.export_mask_image(mask_id) == before
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()
