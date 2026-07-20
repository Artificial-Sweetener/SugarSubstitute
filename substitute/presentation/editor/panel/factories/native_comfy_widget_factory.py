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
