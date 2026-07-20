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

"""Build native Comfy value editors through focused presentation owners."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.panel.factories.field_factory import (
    EditorFieldBuildRequest,
    EditorFieldFactoryResult,
)
from substitute.presentation.editor.panel.widgets.fields.native import (
    AudioRecordField,
    BoundingBoxField,
    ColorField,
    CurveField,
)

NativeFieldBuilder = Callable[[object, QWidget | None], QWidget]


class NativeComfyWidgetFactory:
    """Route native structured widget types to their dedicated Fluent fields."""

    _BUILDERS: Mapping[str, NativeFieldBuilder] = {
        "AUDIO_RECORD": AudioRecordField,
        "BOUNDING_BOX": BoundingBoxField,
        "COLOR": ColorField,
        "CURVE": CurveField,
    }

    def build_field_widget(
        self,
        request: EditorFieldBuildRequest,
    ) -> EditorFieldFactoryResult:
        """Build a native editor or decline unrelated field types."""

        field_type = request.field_type
        if not isinstance(field_type, str):
            return None
        builder = self._BUILDERS.get(field_type.upper())
        if builder is None:
            return None
        parent = request.parent if isinstance(request.parent, QWidget) else None
        value = request.value
        if value is None and field_type.upper() != "AUDIO_RECORD":
            value = request.field_meta.get("default")
        return builder(value, parent)


__all__ = ["NativeComfyWidgetFactory"]
