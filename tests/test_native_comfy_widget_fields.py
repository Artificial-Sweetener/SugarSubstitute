"""Verify native Comfy widget factories, Fluent controls, and state binding."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    ColorPickerButton,
    LineEdit,
    PushButton,
    SpinBox,
    Theme,
    ToolButton,
    isDarkTheme,
    setTheme,
)

from substitute.presentation.editor.panel.factories.field_factory import (
    EditorFieldBuildRequest,
)
from substitute.presentation.editor.panel.factories.native_comfy_widget_factory import (
    NativeComfyWidgetFactory,
)
from substitute.presentation.editor.panel.field_state_controller import (
    EditorPanelFieldStateController,
)
from substitute.presentation.editor.panel.widgets.fields.native import (
    AudioRecordField,
    BoundingBoxField,
    ColorField,
    CurveCanvas,
    CurveField,
)


def _ensure_qapp() -> QApplication:
    """Return the shared QApplication required by native fields."""

    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])


@pytest.mark.parametrize(
    ("field_type", "value", "expected_type"),
    [
        ("AUDIO_RECORD", None, AudioRecordField),
        (
            "BOUNDING_BOX",
            {"x": 1, "y": 2, "width": 3, "height": 4},
            BoundingBoxField,
        ),
        ("COLOR", "#123456", ColorField),
        (
            "CURVE",
            {"points": [[0.0, 0.0], [1.0, 1.0]], "interpolation": "linear"},
            CurveField,
        ),
    ],
)
def test_native_factory_builds_every_bundled_native_editable_family(
    field_type: str,
    value: object,
    expected_type: type[QWidget],
) -> None:
    """Native corpus widget types should resolve through one focused factory."""

    _ensure_qapp()
    parent = QWidget()
    widget = NativeComfyWidgetFactory().build_field_widget(
        EditorFieldBuildRequest(
            parent=parent,
            node_name="node",
            key="value",
            value=value,
            field_meta={},
            field_type=field_type,
        )
    )
    try:
        assert isinstance(widget, expected_type)
    finally:
        parent.deleteLater()
        _ensure_qapp().processEvents()


def test_native_fields_compose_qfluent_controls() -> None:
    """Native editors should use QFluent controls wherever equivalents exist."""

    _ensure_qapp()
    parent = QWidget()
    color = ColorField("#123456", parent)
    box = BoundingBoxField({}, parent)
    curve = CurveField({}, parent)
    audio = AudioRecordField(None, parent)
    try:
        assert isinstance(color.line_edit, LineEdit)
        assert isinstance(color.picker, ColorPickerButton)
        assert isinstance(box, PushButton)
        assert isinstance(curve, PushButton)
        assert isinstance(audio.record_button, ToolButton)
        assert isinstance(audio.choose_button, ToolButton)
        assert box.findChildren(SpinBox) == []
    finally:
        parent.deleteLater()
        _ensure_qapp().processEvents()


def test_native_value_fields_normalize_and_round_trip_values() -> None:
    """Structured native fields should preserve their complete semantic values."""

    _ensure_qapp()
    parent = QWidget()
    color = ColorField("invalid", parent)
    box = BoundingBoxField({"x": 4.5, "width": -2}, parent)
    curve = CurveField(
        {
            "points": [[1.2, -1], [0.25, 0.75], [0, 0]],
            "interpolation": "linear",
        },
        parent,
    )
    audio = AudioRecordField("sample.wav", parent)
    try:
        assert color.value() == "#ffffff"
        assert box.value() == {"x": 4, "y": 0, "width": 0, "height": 512}
        assert curve.value() == {
            "points": [[0.0, 0.0], [0.25, 0.75], [1.0, 0.0]],
            "interpolation": "linear",
        }
        assert audio.value() == "sample.wav"
    finally:
        parent.deleteLater()
        _ensure_qapp().processEvents()


def test_native_semantic_value_signal_persists_through_field_state_owner() -> None:
    """Custom native values should use the same cube-state owner as scalar fields."""

    _ensure_qapp()
    field = ColorField("#000000")
    field.setProperty(
        "input_metadata",
        {
            "cube_alias": "A",
            "node_name": "node",
            "key": "color",
            "type": "COLOR",
        },
    )
    cube_state = SimpleNamespace(
        buffer={"nodes": {"node": {"inputs": {"color": "#000000"}}}},
        dirty=False,
        field_control_states={},
    )
    controller = EditorPanelFieldStateController()
    try:
        controller.bind_node_widget_state(
            field,
            cube_state,
            {"node_name": "node", "key": "color"},
        )
        field.valueChanged.emit("#abcdef")

        assert cube_state.buffer["nodes"]["node"]["inputs"]["color"] == "#abcdef"
        assert cube_state.dirty is True
    finally:
        field.deleteLater()
        _ensure_qapp().processEvents()


def test_native_factory_declines_unknown_custom_socket_type() -> None:
    """Third-party socket types should remain graceful factory misses."""

    result = NativeComfyWidgetFactory().build_field_widget(
        EditorFieldBuildRequest(
            parent=object(),
            node_name="node",
            key="value",
            value=None,
            field_meta={},
            field_type="THIRD_PARTY_SOCKET",
        )
    )

    assert result is None


class _ObservedCurveCanvas(CurveCanvas):
    """Count live theme repaint requests made through the shared theme owner."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize repaint observations before theme wiring runs."""

        self.repaint_requests = 0
        super().__init__({}, parent)

    def update(self, *args: object) -> None:
        """Record and forward one QWidget repaint request."""

        self.repaint_requests += 1
        super().update(*args)


def test_curve_canvas_renders_light_dark_and_refreshes_live_theme() -> None:
    """The custom no-equivalent canvas should repaint with both QFluent themes."""

    app = _ensure_qapp()
    previous_theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
    parent = QWidget()
    canvas = _ObservedCurveCanvas(parent)
    canvas.resize(440, 260)
    parent.resize(460, 280)
    parent.show()
    try:
        setTheme(Theme.DARK)
        app.processEvents()
        dark_image = canvas.grab().toImage()
        requests_before_switch = canvas.repaint_requests

        setTheme(Theme.LIGHT)
        app.processEvents()
        light_image = canvas.grab().toImage()

        assert not isDarkTheme()
        assert canvas.repaint_requests > requests_before_switch
        assert dark_image.pixelColor(20, 20) != light_image.pixelColor(20, 20)
    finally:
        setTheme(previous_theme)
        parent.close()
        parent.deleteLater()
        app.processEvents()
