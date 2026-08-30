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

"""Verify factory routing for native Comfy field families."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.panel.factories.field_factory import (
    EditorFieldBuildRequest,
)
from substitute.presentation.editor.panel.factories.native_comfy_widget_factory import (
    NativeComfyWidgetFactory,
)
from substitute.presentation.editor.panel.widgets.fields.native import (
    AudioRecordField,
    BoundingBoxField,
    ColorField,
    ColorsField,
    CurveField,
)
from tests.support.qt.lifecycle import destroy_qt_object


def _ensure_qapp() -> QApplication:
    """Return the shared QApplication required by native factory outputs."""

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
        ("COLORS", ["#123456", "#abcdef"], ColorsField),
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
    """Resolve every bundled native widget through the focused factory."""

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
        destroy_qt_object(parent)


def test_native_factory_declines_unknown_custom_socket_type() -> None:
    """Leave third-party socket types as graceful factory misses."""

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
