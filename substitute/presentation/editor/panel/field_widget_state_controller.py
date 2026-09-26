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

"""Bind concrete editor widget families to authoritative field values."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from substitute.presentation.editor.panel.choice_field_state_controller import (
    ChoiceFieldStateController,
    string_signal,
)
from substitute.presentation.editor.panel.current_field_state_resolver import (
    CurrentEditorFieldStateResolver,
)
from substitute.presentation.editor.panel.field_state_binding import (
    EditorFieldBinding,
)
from substitute.presentation.editor.panel.field_value_store import (
    EditorFieldValueStore,
)
from substitute.presentation.editor.panel.prompt_field_state_controller import (
    connect_signal,
)
from substitute.presentation.editor.panel.seed_field_state_controller import (
    SeedFieldStateController,
    SeedModeControl,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.field_state_controller")

GetValueFunc = Callable[[Any], Any]
SetValueFunc = Callable[[Any, Any], None]
BufferValueCast = Callable[[Any], Any]


class FieldWidgetStateController:
    """Restore field widgets and persist their emitted values."""

    def __init__(
        self,
        value_store: EditorFieldValueStore,
        state_resolver: CurrentEditorFieldStateResolver,
    ) -> None:
        """Compose generic, choice, and seed field binding collaborators."""

        self._value_store = value_store
        self._state_resolver = state_resolver
        self._choice_fields = ChoiceFieldStateController(value_store, state_resolver)
        self._seed_fields = SeedFieldStateController(mark_dirty)

    def wire_widget_state(
        self,
        widget: object,
        cube_state: object,
        get_val_func: GetValueFunc,
        set_val_func: SetValueFunc,
        signal: object,
        buffer_val_cast: BufferValueCast | None = None,
    ) -> None:
        """Bind one widget's display value and change signal to cube field state."""

        binding = EditorFieldBinding.from_widget(widget)
        if binding is None:
            log_warning(
                _LOGGER,
                "Skipping widget wiring without input metadata",
                widget_type=widget.__class__.__name__,
            )
            return
        try:
            buffer_value = self._value_store.display_value(cube_state, binding)
            if buffer_value is not None:
                if buffer_val_cast is not None:
                    buffer_value = buffer_val_cast(buffer_value)
                if get_val_func(widget) != buffer_value:
                    set_val_func(widget, buffer_value)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            log_warning(
                _LOGGER,
                "Failed to restore widget value from buffer",
                node_name=binding.node_name or "",
                field_key=binding.field_key,
                error_type=type(error).__name__,
            )

        def on_changed(*args: object) -> None:
            """Persist one changed widget value."""

            out_value = args[0] if args else get_val_func(widget)
            try:
                if buffer_val_cast is not None:
                    out_value = buffer_val_cast(out_value)
            except (TypeError, ValueError):
                log_warning(
                    _LOGGER,
                    "Rejected invalid widget value",
                    node_name=binding.node_name or "",
                    field_key=binding.field_key,
                    widget_type=widget.__class__.__name__,
                )
                return
            self._value_store.set_field_value(
                self._state_resolver.resolve(cube_state, binding.cube_alias),
                binding,
                out_value,
            )

        connect_signal(signal, on_changed)

    def wire_numeric_state(self, widget: object, cube_state: object) -> None:
        """Bind a numeric widget exposing value and valueChanged."""

        self.wire_widget_state(
            widget,
            cube_state,
            get_val_func=lambda field: field.value(),
            set_val_func=lambda field, value: field.setValue(value),
            signal=getattr(widget, "valueChanged"),
        )

    def wire_combo_state(self, combo: object, cube_state: object) -> None:
        """Bind a combo-box selection to cube field state."""

        binding = EditorFieldBinding.from_widget(combo)
        if binding is None:
            log_warning(
                _LOGGER,
                "Skipping combo wiring without input metadata",
                widget_type=combo.__class__.__name__,
            )
            return
        if self._choice_fields.bind_linked_choice(combo, cube_state, binding):
            return
        self.wire_text_choice_state(combo, cube_state)

    def wire_text_choice_state(self, widget: object, cube_state: object) -> None:
        """Bind a text-backed choice widget to cube field state."""

        self.wire_widget_state(
            widget,
            cube_state,
            get_val_func=lambda field: field.currentText(),
            set_val_func=lambda field, value: field.setCurrentText(str(value)),
            signal=string_signal(getattr(widget, "currentTextChanged")),
            buffer_val_cast=str,
        )

    def wire_line_edit_state(self, line_edit: object, cube_state: object) -> None:
        """Bind a line-edit value to cube field state."""

        binding = EditorFieldBinding.from_widget(line_edit)
        is_integer_field = binding is not None and binding.field_type == "INT"
        self.wire_widget_state(
            line_edit,
            cube_state,
            get_val_func=lambda field: field.text(),
            set_val_func=lambda field, value: field.setText(str(value)),
            signal=(
                getattr(line_edit, "editingFinished")
                if is_integer_field
                else getattr(line_edit, "textChanged")
            ),
            buffer_val_cast=int if is_integer_field else str,
        )

    def wire_checked_state(self, widget: object, cube_state: object) -> None:
        """Bind a boolean checked widget to cube field state."""

        signal = getattr(widget, "stateChanged", None)
        if signal is None:
            signal = getattr(widget, "checkedChanged")
        self.wire_widget_state(
            widget,
            cube_state,
            get_val_func=lambda field: bool(field.isChecked()),
            set_val_func=lambda field, value: field.setChecked(bool(value)),
            signal=signal,
            buffer_val_cast=bool,
        )

    def wire_seed_state(self, seed_box: object, cube_state: object) -> None:
        """Bind a seed widget's value and control mode to cube field state."""

        self.wire_numeric_state(seed_box, cube_state)
        binding = EditorFieldBinding.from_widget(seed_box)
        if binding is None or binding.node_name is None:
            return
        self._seed_fields.bind_mode(
            cast(SeedModeControl, seed_box),
            cube_state,
            binding,
            state_resolver=lambda: self._state_resolver.resolve(
                cube_state,
                binding.cube_alias,
            ),
        )

    def restore_image_picker(self, image_picker: object, cube_state: object) -> None:
        """Restore an image-picker thumbnail without owning its action writes."""

        binding = EditorFieldBinding.from_widget(image_picker)
        if binding is None:
            log_warning(
                _LOGGER,
                "Skipping image picker restore without input metadata",
                widget_type=image_picker.__class__.__name__,
            )
            return
        try:
            buffer_value = self._value_store.field_value(cube_state, binding)
            if (
                isinstance(buffer_value, str)
                and buffer_value
                and getattr(image_picker, "current_file_path")() != buffer_value
            ):
                getattr(image_picker, "set_thumbnail")(buffer_value)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            log_warning(
                _LOGGER,
                "Failed to restore image picker value from buffer",
                node_name=binding.node_name or "",
                field_key=binding.field_key,
                error_type=type(error).__name__,
            )

    def wire_mask_picker_state(self, mask_picker: object, cube_state: object) -> None:
        """Bind a mask-picker path to cube field state."""

        binding = EditorFieldBinding.from_widget(mask_picker)
        if binding is None:
            log_warning(
                _LOGGER,
                "Skipping mask picker wiring without input metadata",
                widget_type=mask_picker.__class__.__name__,
            )
            return
        current = self._value_store.display_value(cube_state, binding)
        if isinstance(current, str) and current:
            set_mask_path = getattr(mask_picker, "set_mask_path", None)
            if callable(set_mask_path):
                set_mask_path(current)

        def on_mask_selected(*args: object) -> None:
            """Persist the selected mask path from the picker signal."""

            path = args[-1] if args else getattr(mask_picker, "current_file_path")()
            self._value_store.set_field_value(
                self._state_resolver.resolve(cube_state, binding.cube_alias),
                binding,
                str(path),
            )

        connect_signal(getattr(mask_picker, "maskSelected"), on_mask_selected)


def mark_dirty(cube_state: object) -> None:
    """Mark seed-owning cube state dirty through its public attribute."""

    if hasattr(cube_state, "dirty"):
        setattr(cube_state, "dirty", True)


__all__ = [
    "BufferValueCast",
    "FieldWidgetStateController",
    "GetValueFunc",
    "SetValueFunc",
]
