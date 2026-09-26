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

"""Route editor field widgets to focused state owners."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import sys
from typing import cast

try:
    from qfluentwidgets import CheckBox, LineEdit  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight import stubs.

    class CheckBox:  # type: ignore[no-redef]
        """Fallback checkbox type used by lightweight import tests."""

    class LineEdit:  # type: ignore[no-redef]
        """Fallback line-edit type used by lightweight import tests."""


from substitute.presentation.editor.panel.current_field_state_resolver import (
    CurrentEditorFieldStateResolver,
)
from substitute.presentation.editor.panel.field_state_binding import EditorFieldBinding
from substitute.presentation.editor.panel.field_value_store import EditorFieldValueStore
from substitute.presentation.editor.panel.field_widget_state_controller import (
    BufferValueCast,
    FieldWidgetStateController,
    GetValueFunc,
    SetValueFunc,
)
from substitute.presentation.editor.panel.prompt_field_state_controller import (
    EditorPanelFieldStateHost,
    PromptFieldStateController,
    set_prompt_editor_source_text,
)

_QTGUI_MODULE = sys.modules.get("PySide6.QtGui")
_QTGUI_LIGHTWEIGHT_STUB = _QTGUI_MODULE is not None and not hasattr(
    _QTGUI_MODULE,
    "QFocusEvent",
)

try:
    from substitute.presentation.widgets import (
        ComboBox,
        DoubleSpinBox,
        SeedBox,
        SpinBox,
    )
except ImportError:  # pragma: no cover - lightweight import stubs.

    class ComboBox:  # type: ignore[no-redef]
        """Fallback combo-box type used by lightweight import tests."""

    class DoubleSpinBox:  # type: ignore[no-redef]
        """Fallback double-spinbox type used by lightweight import tests."""

    class SeedBox:  # type: ignore[no-redef]
        """Fallback seedbox type used by lightweight import tests."""

    class SpinBox:  # type: ignore[no-redef]
        """Fallback spinbox type used by lightweight import tests."""


try:
    if _QTGUI_LIGHTWEIGHT_STUB:
        raise ImportError
    from substitute.presentation.widgets.model_picker import ModelPickerField
except ImportError:  # pragma: no cover - lightweight import stubs.

    class ModelPickerField:  # type: ignore[no-redef]
        """Fallback model-picker type used by lightweight import tests."""


try:
    from substitute.presentation.editor.prompt_editor import PromptEditor
except ImportError:  # pragma: no cover - lightweight import stubs.

    class PromptEditor:  # type: ignore[no-redef]
        """Fallback prompt-editor type used by lightweight import tests."""


try:
    from .widgets.fields.load_image import ImagePicker
except ImportError:  # pragma: no cover - lightweight import stubs.

    class ImagePicker:  # type: ignore[no-redef]
        """Fallback image-picker type used by lightweight import tests."""


try:
    from .widgets.fields.load_mask import MaskPicker
except ImportError:  # pragma: no cover - lightweight import stubs.

    class MaskPicker:  # type: ignore[no-redef]
        """Fallback mask-picker type used by lightweight import tests."""


class EditorPanelFieldStateController:
    """Coordinate widget dispatch across focused editor field-state owners."""

    def __init__(
        self,
        host: EditorPanelFieldStateHost | None = None,
        *,
        field_value_changed: Callable[[EditorFieldBinding, object], None] | None = None,
    ) -> None:
        """Compose value, prompt, and widget-family state owners."""

        self._value_store = EditorFieldValueStore(field_value_changed)
        self._current_state_resolver = CurrentEditorFieldStateResolver(host)
        self._widget_state = FieldWidgetStateController(
            self._value_store,
            self._current_state_resolver,
        )
        self._prompt_state = PromptFieldStateController(
            host,
            self._value_store,
            self._current_state_resolver,
            PromptEditor,
        )

    def bind_node_widget_state(
        self,
        widget: object,
        cube_state: object,
        metadata: Mapping[str, object],
        *,
        manual_prompt_height_changed: Callable[[], None] | None = None,
    ) -> None:
        """Route one node widget to its concrete state adapter."""

        self._ensure_widget_metadata(widget, metadata)
        if hasattr(widget, "spinbox"):
            spinbox = cast(object, getattr(widget, "spinbox"))
            self._ensure_widget_metadata(spinbox, metadata)
            if isinstance(spinbox, (DoubleSpinBox, SpinBox)):
                self._widget_state.wire_numeric_state(spinbox, cube_state)
                return
        if isinstance(widget, PromptEditor):
            self.wire_prompt_editor_state(
                widget,
                cube_state,
                manual_height_changed=manual_prompt_height_changed,
            )
            return
        if isinstance(widget, SeedBox):
            self._widget_state.wire_seed_state(widget, cube_state)
            return
        if isinstance(widget, (DoubleSpinBox, SpinBox)):
            self._widget_state.wire_numeric_state(widget, cube_state)
            return
        if isinstance(widget, ModelPickerField):
            self._widget_state.wire_text_choice_state(widget, cube_state)
            return
        if isinstance(widget, ComboBox):
            self._widget_state.wire_combo_state(widget, cube_state)
            return
        if isinstance(widget, LineEdit):
            self._widget_state.wire_line_edit_state(widget, cube_state)
            return
        if isinstance(widget, CheckBox):
            self._widget_state.wire_checked_state(widget, cube_state)
            return
        if isinstance(widget, ImagePicker):
            self._widget_state.restore_image_picker(widget, cube_state)
            return
        if isinstance(widget, MaskPicker):
            self._widget_state.wire_mask_picker_state(widget, cube_state)
            return
        if self._wire_semantic_value_widget_state(widget, cube_state):
            return
        if widget.__class__.__name__ == "SwitchButton":
            self._widget_state.wire_checked_state(widget, cube_state)

    def sync_prompt_editor_values_from_buffers(self) -> None:
        """Restore all prompt editors from authoritative buffers."""

        self._prompt_state.sync_all_from_buffers()

    def sync_prompt_editor_values_for_cube(self, cube_alias: str) -> None:
        """Restore prompt editors for one cube alias."""

        self._prompt_state.sync_cube_from_buffers(cube_alias)

    def sync_prompt_editor_values_for_widget(self, cube_widget: object) -> None:
        """Restore prompt editors mounted under one cube widget."""

        self._prompt_state.sync_widget_from_buffers(cube_widget)

    def wire_widget_state(
        self,
        widget: object,
        cube_state: object,
        get_val_func: GetValueFunc,
        set_val_func: SetValueFunc,
        signal: object,
        buffer_val_cast: BufferValueCast | None = None,
    ) -> None:
        """Bind a generic value widget through the widget-state owner."""

        self._widget_state.wire_widget_state(
            widget,
            cube_state,
            get_val_func,
            set_val_func,
            signal,
            buffer_val_cast,
        )

    def field_value(self, cube_state: object, binding: EditorFieldBinding) -> object:
        """Return one persisted field value."""

        return self._value_store.field_value(cube_state, binding)

    def display_value(self, cube_state: object, binding: EditorFieldBinding) -> object:
        """Return one field's initial display value."""

        return self._value_store.display_value(cube_state, binding)

    def set_field_value(
        self,
        cube_state: object,
        binding: EditorFieldBinding,
        value: object,
    ) -> bool:
        """Persist one field value through the value-store owner."""

        return self._value_store.set_field_value(cube_state, binding, value)

    def wire_prompt_editor_state(
        self,
        prompt_editor: object,
        cube_state: object,
        *,
        manual_height_changed: Callable[[], None] | None = None,
    ) -> None:
        """Bind prompt text and its presentation preferences."""

        binding = EditorFieldBinding.from_widget(prompt_editor)
        if binding is not None:
            self._prompt_state.bind_preferences(
                prompt_editor,
                cube_state,
                binding,
                manual_height_changed=manual_height_changed,
            )
        self._widget_state.wire_widget_state(
            prompt_editor,
            cube_state,
            get_val_func=lambda widget: widget.toPlainText(),
            set_val_func=lambda widget, value: set_prompt_editor_source_text(
                widget,
                str(value),
            ),
            signal=getattr(prompt_editor, "textChanged"),
            buffer_val_cast=str,
        )

    def wire_combobox_state(self, combo: object, cube_state: object) -> None:
        """Bind one combo box through choice-state policy."""

        self._widget_state.wire_combo_state(combo, cube_state)

    def wire_model_picker_state(self, model_picker: object, cube_state: object) -> None:
        """Bind one model picker through text-choice state."""

        self._widget_state.wire_text_choice_state(model_picker, cube_state)

    def wire_imagepicker_state(self, image_picker: object, cube_state: object) -> None:
        """Restore one image picker through the widget-state owner."""

        self._widget_state.restore_image_picker(image_picker, cube_state)

    def wire_lineedit_state(self, line_edit: object, cube_state: object) -> None:
        """Bind one line edit through scalar widget-state policy."""

        self._widget_state.wire_line_edit_state(line_edit, cube_state)

    def _wire_semantic_value_widget_state(
        self,
        widget: object,
        cube_state: object,
    ) -> bool:
        """Bind a custom field exposing value, setValue, and valueChanged."""

        value_reader = getattr(widget, "value", None)
        value_writer = getattr(widget, "setValue", None)
        value_changed = getattr(widget, "valueChanged", None)
        if (
            not callable(value_reader)
            or not callable(value_writer)
            or value_changed is None
            or not hasattr(value_changed, "connect")
        ):
            return False
        self._widget_state.wire_numeric_state(widget, cube_state)
        return True

    @staticmethod
    def _ensure_widget_metadata(
        widget: object,
        metadata: Mapping[str, object],
    ) -> None:
        """Attach minimal input metadata when the widget lacks full metadata."""

        property_getter = getattr(widget, "property", None)
        set_property = getattr(widget, "setProperty", None)
        if not callable(set_property):
            return
        current = (
            property_getter("input_metadata") if callable(property_getter) else None
        )
        if current:
            return
        set_property(
            "input_metadata",
            {"node_name": metadata.get("node_name"), "key": metadata.get("key")},
        )


__all__ = ["EditorPanelFieldStateController"]
