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

"""Verify native Comfy widget factories, Fluent controls, and state binding."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QTranslator
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QMediaRecorder
from PySide6.QtWidgets import QApplication, QFileDialog, QWidget
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
from substitute.presentation.editor.panel.widgets.fields.native.bounding_box_field import (
    _BoundingBoxDialog,
)
from substitute.presentation.editor.panel.widgets.fields.native.curve_field import (
    _CurveDialog,
)
from substitute.presentation.dialogs import (
    LocalizedColorDialog,
    LocalizedColorPickerButton,
    LocalizedMessageBoxBase,
)
from substitute.presentation.localization import (
    LocalizedCaptionLabel,
    LocalizedPushButton,
    LocalizedSubtitleLabel,
)
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.fluent_tooltips import FluentToolTipFilter


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


def test_native_fields_retranslate_in_place_without_losing_values() -> None:
    """Switch app-owned chrome while preserving every mounted native field value."""

    app = _ensure_qapp()
    parent = QWidget()
    audio = AudioRecordField(None, parent)
    box = BoundingBoxField({"x": 1, "y": 2, "width": 3, "height": 4}, parent)
    curve = CurveField(
        {"points": [[0.0, 0.0], [0.5, 0.7], [1.0, 1.0]]},
        parent,
    )
    color = ColorField("#123456", parent)
    identities = tuple(
        map(id, (audio, box, curve, color, color.line_edit, color.picker))
    )
    translator = _DictionaryTranslator(_JAPANESE_NATIVE_TRANSLATIONS)
    try:
        assert audio.status_label.text() == "No audio"
        assert box.text() == "x 1 · y 2 · 3×4"
        assert curve.text() == "Edit curve (3 points)"
        assert color.picker.toolTip() == "Choose color"

        assert app.installTranslator(translator)
        _send_language_change(parent)

        assert (
            tuple(map(id, (audio, box, curve, color, color.line_edit, color.picker)))
            == identities
        )
        assert audio.status_label.text() == "音声なし"
        assert audio.record_button.toolTip() == "デフォルトのマイクで音声を録音"
        assert audio.choose_button.toolTip() == "既存の音声ファイルを選択"
        assert isinstance(
            getattr(
                audio.record_button,
                "_sugarsubstitute_fluent_tooltip_filter",
                None,
            ),
            FluentToolTipFilter,
        )
        assert box.text() == "x 1・y 2・3×4"
        assert curve.text() == "カーブを編集（3点）"
        assert color.picker.toolTip() == "色を選択"
        assert color.line_edit.text() == "#123456"
        assert box.value() == {"x": 1, "y": 2, "width": 3, "height": 4}
        assert curve.value()["points"] == [[0.0, 0.0], [0.5, 0.7], [1.0, 1.0]]
        assert color.value() == "#123456"
    finally:
        app.removeTranslator(translator)
        parent.deleteLater()
        app.processEvents()


def test_native_audio_localizes_dialogs_and_preserves_unicode_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Translate owned audio copy while retaining selected filenames and diagnostics."""

    app = _ensure_qapp()
    translator = _DictionaryTranslator(_JAPANESE_NATIVE_TRANSLATIONS)
    assert app.installTranslator(translator)
    field = AudioRecordField(None)
    selected_path = "C:/音声/録音.wav"
    captured: dict[str, str] = {}

    def choose_audio(
        _parent: QWidget,
        title: str,
        _directory: str,
        file_filter: str,
    ) -> tuple[str, str]:
        """Capture localized native-dialog copy and return one Unicode path."""

        captured.update(title=title, file_filter=file_filter)
        return selected_path, file_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileName", choose_audio)
    try:
        field._choose_audio_file()

        assert captured == {
            "title": "音声を選択",
            "file_filter": (
                "音声ファイル (*.wav *.mp3 *.flac *.m4a *.ogg);;すべてのファイル (*)"
            ),
        }
        assert field.value() == selected_path
        assert field.status_label.text() == "録音.wav"
        assert field.status_label.toolTip() == selected_path
        assert isinstance(
            getattr(
                field.status_label,
                "_sugarsubstitute_fluent_tooltip_filter",
                None,
            ),
            FluentToolTipFilter,
        )

        field._recording_failed(
            QMediaRecorder.Error.ResourceError,
            "device diagnostic 日本語",
        )
        assert field.status_label.text() == "録音に失敗しました"
        assert field.status_label.toolTip() == "device diagnostic 日本語"
    finally:
        app.removeTranslator(translator)
        field.deleteLater()
        app.processEvents()


def test_native_dialogs_use_complete_localized_qfluent_chrome() -> None:
    """Translate message, color, bounding-box, and curve dialog chrome in place."""

    app = _ensure_qapp()
    parent = QWidget()
    message = LocalizedMessageBoxBase(parent)
    color = LocalizedColorDialog(
        QColor("#123456"),
        app_text("Choose color"),
        parent,
        enable_alpha=True,
    )
    box = _BoundingBoxDialog(
        {"x": 1, "y": 2, "width": 3, "height": 4},
        parent,
    )
    curve = _CurveDialog({}, parent)
    translator = _DictionaryTranslator(_JAPANESE_NATIVE_TRANSLATIONS)
    try:
        assert app.installTranslator(translator)
        for dialog in (message, color, box, curve):
            _send_language_change(dialog)

        assert (message.yesButton.text(), message.cancelButton.text()) == (
            "OK",
            "キャンセル",
        )
        assert color.titleLabel.text() == "色を選択"
        assert color.editLabel.text() == "色を編集"
        assert (
            color.redLabel.text(),
            color.greenLabel.text(),
            color.blueLabel.text(),
            color.opacityLabel.text(),
        ) == ("赤", "緑", "青", "不透明度")
        assert (color.yesButton.text(), color.cancelButton.text()) == (
            "OK",
            "キャンセル",
        )
        assert box.title_label.text() == "バウンディングボックス"
        assert {label.text() for label in box.findChildren(LocalizedCaptionLabel)} >= {
            "X座標",
            "Y座標",
            "幅",
            "高さ",
        }
        assert {
            label.text() for label in curve.findChildren(LocalizedSubtitleLabel)
        } >= {"カーブ"}
        assert {
            label.text() for label in curve.findChildren(LocalizedCaptionLabel)
        } >= {"クリックで点を追加、ドラッグで移動、右クリックで削除します。"}
        assert {
            button.text() for button in curve.findChildren(LocalizedPushButton)
        } >= {"リセット"}
    finally:
        app.removeTranslator(translator)
        for dialog in (message, color, box, curve):
            dialog.close()
            dialog.deleteLater()
        parent.deleteLater()
        app.processEvents()


def test_color_field_uses_the_shared_localized_qfluent_dialog_owner() -> None:
    """Keep the native color field on the same dialog owner used by Settings."""

    _ensure_qapp()
    field = ColorField("#123456")
    try:
        assert isinstance(field.picker, LocalizedColorPickerButton)
        dialog = field.picker._create_color_dialog()
        try:
            assert isinstance(dialog, LocalizedColorDialog)
        finally:
            dialog.close()
            dialog.deleteLater()
    finally:
        field.deleteLater()
        _ensure_qapp().processEvents()


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


def _send_language_change(root: QWidget) -> None:
    """Deliver the same in-place retranslation event used by the app transaction."""

    for target in (root, *root.findChildren(QWidget)):
        QCoreApplication.sendEvent(target, QEvent(QEvent.Type.LanguageChange))


class _DictionaryTranslator(QTranslator):
    """Provide deterministic AppText translations without compiled test catalogs."""

    def __init__(self, translations: dict[str, str]) -> None:
        """Store translations keyed by their authored English source."""

        super().__init__()
        self._translations = translations

    def translate(
        self,
        context: str,
        source_text: str,
        disambiguation: str | None = None,
        n: int = -1,
    ) -> str:
        """Return mapped AppText while ignoring unused plural metadata."""

        del disambiguation, n
        return self._translations.get(source_text, "") if context == "AppText" else ""


_JAPANESE_NATIVE_TRANSLATIONS = {
    "Record audio from the default microphone": "デフォルトのマイクで音声を録音",
    "Choose an existing audio file": "既存の音声ファイルを選択",
    "No microphone": "マイクが見つかりません",
    "Recording…": "録音中…",
    "Recording failed": "録音に失敗しました",
    "Choose audio": "音声を選択",
    "Audio files (*.wav *.mp3 *.flac *.m4a *.ogg);;All files (*)": (
        "音声ファイル (*.wav *.mp3 *.flac *.m4a *.ogg);;すべてのファイル (*)"
    ),
    "No audio": "音声なし",
    "Bounding box": "バウンディングボックス",
    "X coordinate": "X座標",
    "Y coordinate": "Y座標",
    "Width": "幅",
    "Height": "高さ",
    "x %1 · y %2 · %3×%4": "x %1・y %2・%3×%4",
    "Curve": "カーブ",
    "Click to add, drag to move, and right-click to remove a point.": (
        "クリックで点を追加、ドラッグで移動、右クリックで削除します。"
    ),
    "Reset": "リセット",
    "Edit curve (%1 points)": "カーブを編集（%1点）",
    "Choose color": "色を選択",
    "Edit Color": "色を編集",
    "Red": "赤",
    "Green": "緑",
    "Blue": "青",
    "Opacity": "不透明度",
    "OK": "OK",
    "Cancel": "キャンセル",
}
