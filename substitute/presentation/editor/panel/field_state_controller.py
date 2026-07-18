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

"""Own editor-panel workflow field state, widget binding, and dirty marking."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
import sys
from typing import Any, Literal, Protocol, cast, runtime_checkable

from PySide6.QtCore import QTimer

try:
    from qfluentwidgets import CheckBox, LineEdit  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - exercised by lightweight import stubs.

    class CheckBox:  # type: ignore[no-redef]
        """Fallback checkbox type used only when tests stub qfluentwidgets."""

    class LineEdit:  # type: ignore[no-redef]
        """Fallback line-edit type used only when tests stub qfluentwidgets."""


from substitute.application.overrides.link_policy import apply_choice_selection
from substitute.domain.generation.seed_control import SeedControlState
from substitute.presentation.editor.panel.seed_field_state_controller import (
    SeedFieldStateController,
)
from substitute.shared.logging.logger import get_logger, log_warning

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
except ImportError:  # pragma: no cover - exercised by lightweight import stubs.

    class ComboBox:  # type: ignore[no-redef]
        """Fallback combo-box type used only when tests stub Qt modules."""

    class DoubleSpinBox:  # type: ignore[no-redef]
        """Fallback double-spinbox type used only when tests stub Qt modules."""

    class SeedBox:  # type: ignore[no-redef]
        """Fallback seedbox type used only when tests stub Qt modules."""

    class SpinBox:  # type: ignore[no-redef]
        """Fallback spinbox type used only when tests stub Qt modules."""


try:
    if _QTGUI_LIGHTWEIGHT_STUB:
        raise ImportError
    from substitute.presentation.widgets.model_picker import ModelPickerField
except ImportError:  # pragma: no cover - exercised by lightweight import stubs.

    class ModelPickerField:  # type: ignore[no-redef]
        """Fallback model-picker type used only when tests stub Qt modules."""


try:
    from substitute.presentation.editor.prompt_editor import PromptEditor
except ImportError:  # pragma: no cover - exercised by lightweight import stubs.

    class PromptEditor:  # type: ignore[no-redef]
        """Fallback prompt-editor type used only when tests stub Qt modules."""


try:
    from .widgets.fields.load_image import ImagePicker
except ImportError:  # pragma: no cover - exercised by lightweight import stubs.

    class ImagePicker:  # type: ignore[no-redef]
        """Fallback image-picker type used only when tests stub Qt modules."""


try:
    from .widgets.fields.load_mask import MaskPicker
except ImportError:  # pragma: no cover - exercised by lightweight import stubs.

    class MaskPicker:  # type: ignore[no-redef]
        """Fallback mask-picker type used only when tests stub Qt modules."""


_LOGGER = get_logger("presentation.editor.panel.field_state_controller")
NODE_STATE_KEYS = frozenset({"enabled"})
_PROMPT_EDITOR_MANUAL_HEIGHTS_UI_KEY = "prompt_editor_manual_heights"
_PROMPT_EDITOR_RICH_RENDERING_UI_KEY = "prompt_editor_rich_rendering"
_DISPLAY_FALLBACK_VALUE_SOURCES = frozenset({"first_option", "live_default"})

FieldStorageKind = Literal["input", "node"]
GetValueFunc = Callable[[Any], Any]
SetValueFunc = Callable[[Any, Any], None]
BufferValueCast = Callable[[Any], Any]


class FieldStateCubeStateProtocol(Protocol):
    """Describe cube-state payload access used by field-state persistence."""

    buffer: dict[str, Any]
    dirty: bool
    field_control_states: dict[str, dict[str, SeedControlState]]


class EditorPanelFieldStateHost(Protocol):
    """Describe panel state required for prompt field-state restoration."""

    cube_widgets: Mapping[str, object]
    _cube_states: Mapping[str, FieldStateCubeStateProtocol] | None


@runtime_checkable
class _ValueWritable(Protocol):
    """Describe lightweight widgets that accept a numeric/object value."""

    def setValue(self, value: object) -> None:  # noqa: N802
        """Set the current widget value."""


@dataclass(frozen=True, slots=True)
class EditorFieldBinding:
    """Identify one editor field and how its value is stored."""

    cube_alias: str | None
    node_name: str | None
    field_key: str
    storage_kind: FieldStorageKind
    value_source: str | None
    resolved_display_value: object | None
    prompt_field_identity: str | None
    node_type: str | None = None
    field_type: str | None = None

    @classmethod
    def from_metadata(cls, metadata: object) -> EditorFieldBinding | None:
        """Create a typed field binding from sanitized Qt input metadata."""

        if not isinstance(metadata, Mapping):
            return None
        raw_key = metadata.get("key")
        if not isinstance(raw_key, str) or not raw_key.strip():
            return None
        raw_node_name = metadata.get("node_name")
        node_name = raw_node_name if isinstance(raw_node_name, str) else None
        raw_cube_alias = metadata.get("cube_alias")
        cube_alias = raw_cube_alias if isinstance(raw_cube_alias, str) else None
        value_source = metadata.get("value_source")
        node_type = metadata.get("node_type")
        field_type = metadata.get("type")
        field_key = raw_key.strip()
        prompt_identity = (
            f"{node_name.strip()}.{field_key}"
            if isinstance(node_name, str) and node_name.strip()
            else None
        )
        return cls(
            cube_alias=cube_alias,
            node_name=node_name,
            field_key=field_key,
            storage_kind="node" if field_key in NODE_STATE_KEYS else "input",
            value_source=value_source if isinstance(value_source, str) else None,
            resolved_display_value=metadata.get("resolved_value"),
            prompt_field_identity=prompt_identity,
            node_type=node_type if isinstance(node_type, str) else None,
            field_type=field_type if isinstance(field_type, str) else None,
        )

    @classmethod
    def from_widget(cls, widget: object) -> EditorFieldBinding | None:
        """Create a typed binding from one widget's Qt metadata."""

        property_getter = getattr(widget, "property", None)
        if not callable(property_getter):
            return None
        return cls.from_metadata(property_getter("input_metadata"))


class EditorPanelFieldStateController:
    """Coordinate editor field value persistence and widget state binding."""

    def __init__(
        self,
        host: EditorPanelFieldStateHost | None = None,
        *,
        field_value_changed: Callable[[EditorFieldBinding, object], None] | None = None,
    ) -> None:
        """Store the optional panel host used for prompt field refreshes."""

        self._host = host
        self._field_value_changed = field_value_changed
        self._seed_field_state = SeedFieldStateController(self._mark_cube_state_dirty)

    def bind_node_widget_state(
        self,
        widget: object,
        cube_state: object,
        metadata: Mapping[str, object],
        *,
        manual_prompt_height_changed: Callable[[], None] | None = None,
    ) -> None:
        """Wire one node widget to authoritative cube field state."""

        self._ensure_widget_metadata(widget, metadata)
        if hasattr(widget, "spinbox"):
            spinbox = cast(object, getattr(widget, "spinbox"))
            self._ensure_widget_metadata(spinbox, metadata)
            if isinstance(spinbox, DoubleSpinBox):
                self.wire_doublespinbox_state(spinbox, cube_state)
                return
            if isinstance(spinbox, SpinBox):
                self.wire_spinbox_state(spinbox, cube_state)
                return

        if isinstance(widget, PromptEditor):
            self.wire_prompt_editor_state(
                widget,
                cube_state,
                manual_height_changed=manual_prompt_height_changed,
            )
            return
        if isinstance(widget, SeedBox):
            self.wire_seedbox_state(widget, cube_state)
            return
        if isinstance(widget, DoubleSpinBox):
            self.wire_doublespinbox_state(widget, cube_state)
            return
        if isinstance(widget, SpinBox):
            self.wire_spinbox_state(widget, cube_state)
            return
        if isinstance(widget, ModelPickerField):
            self.wire_model_picker_state(widget, cube_state)
            return
        if isinstance(widget, ComboBox):
            self.wire_combobox_state(widget, cube_state)
            return
        if isinstance(widget, LineEdit):
            self.wire_lineedit_state(widget, cube_state)
            return
        if isinstance(widget, CheckBox):
            self.wire_checkbox_state(widget, cube_state)
            return
        if isinstance(widget, ImagePicker):
            self.wire_imagepicker_state(widget, cube_state)
            return
        if isinstance(widget, MaskPicker):
            self.wire_maskpicker_state(widget, cube_state)
            return
        if widget.__class__.__name__ == "SwitchButton":
            self.wire_switchbutton_state(widget, cube_state)

    def sync_prompt_editor_values_from_buffers(self) -> None:
        """Restore all prompt-editor widgets from authoritative workflow buffers."""

        host = self._host
        if host is None or not host._cube_states:
            return
        for cube_widget in host.cube_widgets.values():
            self.sync_prompt_editor_values_for_widget(cube_widget)
        self._refresh_prompt_scene_diagnostics_if_available()

    def sync_prompt_editor_values_for_cube(self, cube_alias: str) -> None:
        """Restore prompt-editor widget values for one cube alias."""

        host = self._host
        if host is None or not host._cube_states:
            return
        cube_widget = host.cube_widgets.get(cube_alias)
        if cube_widget is None:
            return
        self.sync_prompt_editor_values_for_widget(cube_widget)
        self._refresh_prompt_scene_diagnostics_if_available()

    def sync_prompt_editor_values_for_widget(self, cube_widget: object) -> None:
        """Restore prompt-editor widget values hosted by one cube widget."""

        host = self._host
        if host is None or not host._cube_states:
            return
        for prompt_editor in self._prompt_editors_in(cube_widget):
            binding = EditorFieldBinding.from_widget(prompt_editor)
            if binding is None or binding.cube_alias is None:
                continue
            cube_state = host._cube_states.get(binding.cube_alias)
            if cube_state is None:
                continue
            text_value = self.field_value(cube_state, binding)
            text = text_value if isinstance(text_value, str) else ""
            if prompt_editor.toPlainText() != text:
                self._set_prompt_editor_source_text(prompt_editor, text)

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
            buffer_value = self.display_value(cube_state, binding)
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
            self.set_field_value(cube_state, binding, out_value)

        self._connect_signal(signal, on_changed)

    def field_value(self, cube_state: object, binding: EditorFieldBinding) -> object:
        """Return the persisted value for one field binding."""

        node = self._node_payload(cube_state, binding)
        if node is None:
            return None
        if binding.storage_kind == "node":
            return node.get(binding.field_key)
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            return None
        return inputs.get(binding.field_key)

    def display_value(
        self,
        cube_state: object,
        binding: EditorFieldBinding,
    ) -> object:
        """Return the initial widget display value for one field binding."""

        if binding.value_source in _DISPLAY_FALLBACK_VALUE_SOURCES:
            return binding.resolved_display_value
        return self.field_value(cube_state, binding)

    def set_field_value(
        self,
        cube_state: object,
        binding: EditorFieldBinding,
        value: object,
    ) -> bool:
        """Persist one field value and mark the cube dirty only on change."""

        node = self._mutable_node_payload(cube_state, binding)
        if node is None:
            return False
        if binding.storage_kind == "node":
            previous = node.get(binding.field_key)
            if previous == value:
                return False
            node[binding.field_key] = value
            self._mark_cube_state_dirty(cube_state)
            self._notify_field_value_changed(binding, value)
            return True

        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            inputs = {}
            node["inputs"] = inputs
        previous = inputs.get(binding.field_key)
        if previous == value:
            return False
        inputs[binding.field_key] = value
        self._mark_cube_state_dirty(cube_state)
        self._notify_field_value_changed(binding, value)
        return True

    def wire_prompt_editor_state(
        self,
        prompt_editor: PromptEditor,
        cube_state: object,
        *,
        manual_height_changed: Callable[[], None] | None = None,
    ) -> None:
        """Bind a prompt editor to prompt text and prompt UI state."""

        binding = EditorFieldBinding.from_widget(prompt_editor)
        if binding is not None and binding.prompt_field_identity is not None:
            self._restore_prompt_editor_rich_rendering(
                prompt_editor,
                cube_state,
                binding.prompt_field_identity,
            )
        self.wire_widget_state(
            prompt_editor,
            cube_state,
            get_val_func=lambda widget: widget.toPlainText(),
            set_val_func=lambda widget, value: self._set_prompt_editor_source_text(
                widget, str(value)
            ),
            signal=prompt_editor.textChanged,
            buffer_val_cast=str,
        )
        if binding is None or binding.prompt_field_identity is None:
            return
        self._connect_rich_rendering_persistence(
            prompt_editor,
            cube_state,
            binding.prompt_field_identity,
            changed_callback=manual_height_changed,
        )
        stored_height = self._stored_prompt_editor_manual_height(
            cube_state,
            binding.prompt_field_identity,
        )

        def connect_manual_height_persistence() -> None:
            """Persist future user-owned prompt height changes for this field."""

            height_changed = getattr(prompt_editor, "manualScrollHeightChanged", None)
            if height_changed is None:
                return

            def persist_manual_height(height: object) -> None:
                """Store one changed prompt height and notify the shell."""

                changed = self._store_prompt_editor_manual_height(
                    cube_state,
                    binding.prompt_field_identity or "",
                    height,
                )
                if changed and manual_height_changed is not None:
                    manual_height_changed()

            self._connect_signal(height_changed, persist_manual_height)

        if stored_height is None:
            connect_manual_height_persistence()
            return

        def apply_restored_manual_height() -> None:
            """Apply restored height after prompt text layout has settled."""

            set_manual_height = getattr(prompt_editor, "setManualScrollHeight", None)
            if callable(set_manual_height):
                set_manual_height(stored_height)
            connect_manual_height_persistence()

        QTimer.singleShot(0, apply_restored_manual_height)

    def wire_spinbox_state(self, spinbox: SpinBox, cube_state: object) -> None:
        """Bind a spinbox value to cube field state."""

        self.wire_widget_state(
            spinbox,
            cube_state,
            get_val_func=lambda widget: widget.value(),
            set_val_func=lambda widget, value: widget.setValue(value),
            signal=spinbox.valueChanged,
        )

    def wire_doublespinbox_state(
        self,
        doublespinbox: DoubleSpinBox,
        cube_state: object,
    ) -> None:
        """Bind a double-spinbox value to cube field state."""

        self.wire_widget_state(
            doublespinbox,
            cube_state,
            get_val_func=lambda widget: widget.value(),
            set_val_func=lambda widget, value: widget.setValue(value),
            signal=doublespinbox.valueChanged,
        )

    def wire_combobox_state(self, combo: ComboBox, cube_state: object) -> None:
        """Bind a combo-box selection to cube field state."""

        binding = EditorFieldBinding.from_widget(combo)
        if binding is None:
            log_warning(
                _LOGGER,
                "Skipping combo wiring without input metadata",
                widget_type=combo.__class__.__name__,
            )
            return
        if self._bind_linked_choice_combo(combo, cube_state, binding):
            return
        self.wire_widget_state(
            combo,
            cube_state,
            get_val_func=lambda widget: widget.currentText(),
            set_val_func=lambda widget, value: widget.setCurrentText(str(value)),
            signal=self._string_signal(combo.currentTextChanged),
            buffer_val_cast=str,
        )

    def wire_model_picker_state(
        self,
        model_picker: ModelPickerField,
        cube_state: object,
    ) -> None:
        """Bind a model-picker backend value to cube field state."""

        self.wire_widget_state(
            model_picker,
            cube_state,
            get_val_func=lambda widget: widget.currentText(),
            set_val_func=lambda widget, value: widget.setCurrentText(str(value)),
            signal=self._string_signal(model_picker.currentTextChanged),
            buffer_val_cast=str,
        )

    def wire_lineedit_state(self, lineedit: LineEdit, cube_state: object) -> None:
        """Bind a line-edit value to cube field state."""

        binding = EditorFieldBinding.from_widget(lineedit)
        is_integer_field = binding is not None and binding.field_type == "INT"
        self.wire_widget_state(
            lineedit,
            cube_state,
            get_val_func=lambda widget: widget.text(),
            set_val_func=lambda widget, value: widget.setText(str(value)),
            signal=lineedit.editingFinished
            if is_integer_field
            else lineedit.textChanged,
            buffer_val_cast=int if is_integer_field else str,
        )

    def wire_checkbox_state(self, checkbox: CheckBox, cube_state: object) -> None:
        """Bind a checkbox value to cube field state."""

        self.wire_widget_state(
            checkbox,
            cube_state,
            get_val_func=lambda widget: bool(widget.isChecked()),
            set_val_func=lambda widget, value: widget.setChecked(bool(value)),
            signal=checkbox.stateChanged,
            buffer_val_cast=bool,
        )

    def wire_switchbutton_state(self, switch: object, cube_state: object) -> None:
        """Bind a switch-style button value to cube field state."""

        self.wire_widget_state(
            switch,
            cube_state,
            get_val_func=lambda widget: bool(widget.isChecked()),
            set_val_func=lambda widget, value: widget.setChecked(bool(value)),
            signal=getattr(switch, "checkedChanged"),
            buffer_val_cast=bool,
        )

    def wire_seedbox_state(self, seedbox: SeedBox, cube_state: object) -> None:
        """Bind a seedbox value to cube field state."""

        self.wire_widget_state(
            seedbox,
            cube_state,
            get_val_func=lambda widget: widget.value(),
            set_val_func=lambda widget, value: widget.setValue(value),
            signal=seedbox.valueChanged,
        )
        binding = EditorFieldBinding.from_widget(seedbox)
        if binding is None or binding.node_name is None:
            return
        self._seed_field_state.bind_mode(seedbox, cube_state, binding)

    def wire_imagepicker_state(
        self,
        imagepicker: ImagePicker,
        cube_state: object,
    ) -> None:
        """Restore image-picker thumbnails while writes route through panel actions."""

        binding = EditorFieldBinding.from_widget(imagepicker)
        if binding is None:
            log_warning(
                _LOGGER,
                "Skipping image picker restore without input metadata",
                widget_type=imagepicker.__class__.__name__,
            )
            return
        try:
            buffer_value = self.field_value(cube_state, binding)
            if (
                isinstance(buffer_value, str)
                and buffer_value
                and imagepicker.current_file_path() != buffer_value
            ):
                imagepicker.set_thumbnail(buffer_value)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            log_warning(
                _LOGGER,
                "Failed to restore image picker value from buffer",
                node_name=binding.node_name or "",
                field_key=binding.field_key,
                error_type=type(error).__name__,
            )

    def wire_maskpicker_state(self, maskpicker: MaskPicker, cube_state: object) -> None:
        """Bind a mask-picker path to cube field state."""

        binding = EditorFieldBinding.from_widget(maskpicker)
        if binding is None:
            log_warning(
                _LOGGER,
                "Skipping mask picker wiring without input metadata",
                widget_type=maskpicker.__class__.__name__,
            )
            return
        current = self.display_value(cube_state, binding)
        if isinstance(current, str) and current:
            set_mask_path = getattr(maskpicker, "set_mask_path", None)
            if callable(set_mask_path):
                set_mask_path(current)

        def on_mask_selected(*args: object) -> None:
            """Persist the selected mask path from the picker signal."""

            path = args[-1] if args else maskpicker.current_file_path()
            self.set_field_value(cube_state, binding, str(path))

        self._connect_signal(maskpicker.maskSelected, on_mask_selected)

    def _bind_linked_choice_combo(
        self,
        combo: ComboBox,
        cube_state: object,
        binding: EditorFieldBinding,
    ) -> bool:
        """Bind sampler/scheduler link-aware combo selections when applicable."""

        link_key = (
            "sampler_link"
            if binding.field_key == "sampler_name"
            else "scheduler_link"
            if binding.field_key == "scheduler"
            else None
        )
        if link_key is None:
            return False
        node = self._node_payload(cube_state, binding)
        if node is None:
            return False
        label_to_value = getattr(combo, "_editor_choice_values_by_label", None)
        if not isinstance(label_to_value, Mapping):
            if not isinstance(node.get(link_key), dict):
                return False

            def on_literal_changed(text: str) -> None:
                """Persist a literal selection and clear the active link."""

                if not text.startswith("🔗 ") and link_key in node:
                    del node[link_key]
                self.set_field_value(cube_state, binding, text)

            self._connect_signal(
                self._string_signal(combo.currentTextChanged), on_literal_changed
            )
            return True

        if not isinstance(node.get(link_key), dict):
            current = self.field_value(cube_state, binding)
            if current is not None and combo.currentText() != str(current):
                combo.setCurrentText(str(current))

        def on_changed(text: str) -> None:
            """Persist the selected literal or link through the field-state owner."""

            selected_value = label_to_value.get(text)
            before = deepcopy(node)
            apply_choice_selection(
                node,
                literal_key=binding.field_key,
                link_key=link_key,
                selected_value=selected_value,
            )
            if node != before:
                self._mark_cube_state_dirty(cube_state)
                self._notify_field_value_changed(
                    binding,
                    self.field_value(cube_state, binding),
                )

        self._connect_signal(self._string_signal(combo.currentTextChanged), on_changed)
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
            {
                "node_name": metadata.get("node_name"),
                "key": metadata.get("key"),
            },
        )

    @staticmethod
    def _prompt_editors_in(cube_widget: object) -> tuple[PromptEditor, ...]:
        """Return prompt-editor children from one cube widget-like object."""

        find_children = getattr(cube_widget, "findChildren", None)
        if not callable(find_children):
            return ()
        return tuple(
            editor
            for editor in find_children(PromptEditor)
            if isinstance(editor, PromptEditor)
        )

    @staticmethod
    def _set_prompt_editor_source_text(prompt_editor: object, text: str) -> None:
        """Restore prompt source text exactly when the editor exposes that API."""

        replace_baseline_source_text = getattr(
            prompt_editor,
            "replaceBaselineSourceText",
            None,
        )
        if callable(replace_baseline_source_text):
            replace_baseline_source_text(text)
            return
        set_source_text = getattr(prompt_editor, "setSourceText", None)
        if callable(set_source_text):
            set_source_text(text)
            return
        set_plain_text = getattr(prompt_editor, "setPlainText")
        set_plain_text(text)

    def _restore_prompt_editor_rich_rendering(
        self,
        prompt_editor: object,
        cube_state: object,
        field_identity: str,
    ) -> None:
        """Apply stored rich-rendering state without marking the cube dirty."""

        stored_enabled = self._stored_prompt_editor_rich_rendering_enabled(
            cube_state,
            field_identity,
        )
        if stored_enabled is None:
            return
        set_enabled = getattr(prompt_editor, "setRichPromptRenderingEnabled", None)
        if callable(set_enabled):
            set_enabled(stored_enabled)

    def _connect_rich_rendering_persistence(
        self,
        prompt_editor: object,
        cube_state: object,
        field_identity: str,
        *,
        changed_callback: Callable[[], None] | None,
    ) -> None:
        """Persist future prompt rich-rendering preference changes for this field."""

        rich_rendering_changed = getattr(
            prompt_editor,
            "richPromptRenderingEnabledChanged",
            None,
        )
        if rich_rendering_changed is None:
            return

        def persist_rich_rendering(enabled: object) -> None:
            """Store one changed prompt rich-rendering preference."""

            changed = self._store_prompt_editor_rich_rendering_enabled(
                cube_state,
                field_identity,
                enabled,
            )
            if changed and changed_callback is not None:
                changed_callback()

        self._connect_signal(rich_rendering_changed, persist_rich_rendering)

    @staticmethod
    def _stored_prompt_editor_manual_height(
        cube_state: object,
        field_identity: str,
    ) -> int | None:
        """Return one valid stored prompt editor height."""

        ui_payload = getattr(cube_state, "ui", None)
        if not isinstance(ui_payload, dict):
            return None
        heights = ui_payload.get(_PROMPT_EDITOR_MANUAL_HEIGHTS_UI_KEY)
        if not isinstance(heights, dict):
            return None
        value = heights.get(field_identity)
        if type(value) is int and value > 0:
            return value
        return None

    @staticmethod
    def _stored_prompt_editor_rich_rendering_enabled(
        cube_state: object,
        field_identity: str,
    ) -> bool | None:
        """Return one valid stored prompt rich-rendering preference."""

        ui_payload = getattr(cube_state, "ui", None)
        if not isinstance(ui_payload, dict):
            return None
        preferences = ui_payload.get(_PROMPT_EDITOR_RICH_RENDERING_UI_KEY)
        if not isinstance(preferences, dict):
            return None
        value = preferences.get(field_identity)
        if value is None:
            return None
        if type(value) is bool:
            return value
        log_warning(
            _LOGGER,
            "Ignored invalid prompt editor rich-rendering preference",
            field_identity=field_identity,
            enabled=repr(value),
        )
        return None

    def _store_prompt_editor_manual_height(
        self,
        cube_state: object,
        field_identity: str,
        height: object,
    ) -> bool:
        """Persist one prompt editor manual height in cube UI metadata."""

        if height is None:
            return self._clear_prompt_editor_manual_height(cube_state, field_identity)
        if type(height) is not int or height <= 0:
            log_warning(
                _LOGGER,
                "Ignored invalid prompt editor manual height",
                field_identity=field_identity,
                height=repr(height),
            )
            return False
        ui_payload = self._mutable_cube_ui_payload(cube_state)
        heights = ui_payload.get(_PROMPT_EDITOR_MANUAL_HEIGHTS_UI_KEY)
        if not isinstance(heights, dict):
            heights = {}
            ui_payload[_PROMPT_EDITOR_MANUAL_HEIGHTS_UI_KEY] = heights
        if heights.get(field_identity) == height:
            return False
        heights[field_identity] = height
        self._mark_cube_state_dirty(cube_state)
        return True

    def _clear_prompt_editor_manual_height(
        self,
        cube_state: object,
        field_identity: str,
    ) -> bool:
        """Remove one stored prompt editor manual height when present."""

        ui_payload = getattr(cube_state, "ui", None)
        if not isinstance(ui_payload, dict):
            return False
        heights = ui_payload.get(_PROMPT_EDITOR_MANUAL_HEIGHTS_UI_KEY)
        if not isinstance(heights, dict) or field_identity not in heights:
            return False
        del heights[field_identity]
        if not heights:
            ui_payload.pop(_PROMPT_EDITOR_MANUAL_HEIGHTS_UI_KEY, None)
        self._mark_cube_state_dirty(cube_state)
        return True

    def _store_prompt_editor_rich_rendering_enabled(
        self,
        cube_state: object,
        field_identity: str,
        enabled: object,
    ) -> bool:
        """Persist one prompt rich-rendering preference in cube UI metadata."""

        if type(enabled) is not bool:
            log_warning(
                _LOGGER,
                "Ignored invalid prompt editor rich-rendering preference change",
                field_identity=field_identity,
                enabled=repr(enabled),
            )
            return False
        if enabled:
            return self._clear_prompt_editor_rich_rendering_enabled(
                cube_state,
                field_identity,
            )
        ui_payload = self._mutable_cube_ui_payload(cube_state)
        preferences = ui_payload.get(_PROMPT_EDITOR_RICH_RENDERING_UI_KEY)
        if not isinstance(preferences, dict):
            preferences = {}
            ui_payload[_PROMPT_EDITOR_RICH_RENDERING_UI_KEY] = preferences
        if preferences.get(field_identity) is False:
            return False
        preferences[field_identity] = False
        self._mark_cube_state_dirty(cube_state)
        return True

    def _clear_prompt_editor_rich_rendering_enabled(
        self,
        cube_state: object,
        field_identity: str,
    ) -> bool:
        """Remove one stored prompt rich-rendering preference when present."""

        ui_payload = getattr(cube_state, "ui", None)
        if not isinstance(ui_payload, dict):
            return False
        preferences = ui_payload.get(_PROMPT_EDITOR_RICH_RENDERING_UI_KEY)
        if not isinstance(preferences, dict) or field_identity not in preferences:
            return False
        del preferences[field_identity]
        if not preferences:
            ui_payload.pop(_PROMPT_EDITOR_RICH_RENDERING_UI_KEY, None)
        self._mark_cube_state_dirty(cube_state)
        return True

    @staticmethod
    def _mutable_cube_ui_payload(cube_state: object) -> dict[str, object]:
        """Return mutable cube UI metadata, creating it when absent."""

        ui_payload = getattr(cube_state, "ui", None)
        if not isinstance(ui_payload, dict):
            ui_payload = {}
            setattr(cube_state, "ui", ui_payload)
        return ui_payload

    @staticmethod
    def _mark_cube_state_dirty(cube_state: object) -> None:
        """Mark cube state dirty when the object supports that attribute."""

        if hasattr(cube_state, "dirty"):
            setattr(cube_state, "dirty", True)

    def _notify_field_value_changed(
        self,
        binding: EditorFieldBinding,
        value: object,
    ) -> None:
        """Notify the host about persisted field changes after buffer mutation."""

        if self._field_value_changed is None:
            return
        try:
            self._field_value_changed(binding, value)
        except Exception as error:
            log_warning(
                _LOGGER,
                "Field value change callback failed",
                node_name=binding.node_name or "",
                field_key=binding.field_key,
                error_type=type(error).__name__,
            )

    @staticmethod
    def _node_payload(
        cube_state: object,
        binding: EditorFieldBinding,
    ) -> dict[str, Any] | None:
        """Return one node payload from cube state when present."""

        buffer = getattr(cube_state, "buffer", None)
        if not isinstance(buffer, dict):
            return None
        nodes = buffer.get("nodes")
        if not isinstance(nodes, dict):
            return None
        node = nodes.get(binding.node_name)
        return cast(dict[str, Any], node) if isinstance(node, dict) else None

    @staticmethod
    def _mutable_node_payload(
        cube_state: object,
        binding: EditorFieldBinding,
    ) -> dict[str, Any] | None:
        """Return a mutable node payload from cube state when possible."""

        buffer = getattr(cube_state, "buffer", None)
        if not isinstance(buffer, dict):
            return None
        nodes = buffer.get("nodes")
        if not isinstance(nodes, dict):
            nodes = {}
            buffer["nodes"] = nodes
        node = nodes.get(binding.node_name)
        if not isinstance(node, dict):
            node = {}
            nodes[binding.node_name] = node
        return cast(dict[str, Any], node)

    def _refresh_prompt_scene_diagnostics_if_available(self) -> None:
        """Refresh scene diagnostics when the panel host exposes that API."""

        refresh = getattr(self._host, "refresh_prompt_scene_diagnostics", None)
        if callable(refresh):
            refresh()

    @staticmethod
    def _connect_signal(signal: object, slot: Callable[..., None]) -> None:
        """Connect one Qt-like signal when it exposes a connect method."""

        connect = getattr(signal, "connect", None)
        if callable(connect):
            connect(slot)

    @staticmethod
    def _string_signal(signal: object) -> object:
        """Return a string overload signal where Qt exposes one."""

        try:
            return signal[str]  # type: ignore[index]
        except (KeyError, TypeError, AttributeError):
            return signal


def set_buffer_value_and_dirty(
    cube_state: object,
    node_name: str,
    key: str,
    value: object,
) -> None:
    """Persist one field value through the field-state owner."""

    binding = EditorFieldBinding(
        cube_alias=None,
        node_name=node_name,
        field_key=key,
        storage_kind="node" if key in NODE_STATE_KEYS else "input",
        value_source=None,
        resolved_display_value=None,
        prompt_field_identity=f"{node_name}.{key}" if node_name else None,
    )
    EditorPanelFieldStateController().set_field_value(cube_state, binding, value)


def write_live_widget_value(widget: object, value: object) -> bool:
    """Write a value to one supported live field widget."""

    target = getattr(widget, "spinbox", widget)
    if isinstance(target, DoubleSpinBox):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        target.setValue(float(value))
        return True
    if isinstance(target, (SeedBox, SpinBox)):
        if not isinstance(value, int) or isinstance(value, bool):
            return False
        target.setValue(value)
        return True
    if isinstance(target, _ValueWritable):
        target.setValue(value)
        return True
    if isinstance(target, (ComboBox, ModelPickerField)):
        target.setCurrentText(str(value))
        return True
    if isinstance(target, LineEdit):
        target.setText(str(value))
        return True
    if isinstance(target, CheckBox):
        target.setChecked(bool(value))
        return True
    if isinstance(target, PromptEditor):
        EditorPanelFieldStateController._set_prompt_editor_source_text(
            target,
            str(value),
        )
        return True
    if target.__class__.__name__ == "SwitchButton":
        set_checked = getattr(target, "setChecked", None)
        if callable(set_checked):
            set_checked(bool(value))
            return True
    return False


def wire_widget_state(
    widget: object,
    cube_state: object,
    get_val_func: GetValueFunc,
    set_val_func: SetValueFunc,
    signal: object,
    buffer_val_cast: BufferValueCast | None = None,
) -> None:
    """Bind one widget through the field-state owner."""

    EditorPanelFieldStateController().wire_widget_state(
        widget,
        cube_state,
        get_val_func,
        set_val_func,
        signal,
        buffer_val_cast,
    )


def wire_any_widget_state(widget: object, cube_state: object) -> None:
    """Bind any supported widget through the field-state owner."""

    metadata = EditorFieldBinding.from_widget(widget)
    if metadata is None:
        raise TypeError(f"Cannot wire unknown widget type: {widget.__class__.__name__}")
    EditorPanelFieldStateController().bind_node_widget_state(
        widget,
        cube_state,
        {
            "node_name": metadata.node_name,
            "key": metadata.field_key,
        },
    )


def bind_node_widget_state(
    widget: object,
    cube_state: object,
    metadata: Mapping[str, object],
    *,
    manual_prompt_height_changed: Callable[[], None] | None = None,
) -> None:
    """Bind one node widget through the field-state owner."""

    EditorPanelFieldStateController().bind_node_widget_state(
        widget,
        cube_state,
        metadata,
        manual_prompt_height_changed=manual_prompt_height_changed,
    )


def wire_prompt_editor_state(
    prompt_editor: PromptEditor,
    cube_state: object,
    *,
    manual_height_changed: Callable[[], None] | None = None,
) -> None:
    """Bind a prompt editor through the field-state owner."""

    EditorPanelFieldStateController().wire_prompt_editor_state(
        prompt_editor,
        cube_state,
        manual_height_changed=manual_height_changed,
    )


def wire_combobox_state(combo: ComboBox, cube_state: object) -> None:
    """Bind a combo box through the field-state owner."""

    EditorPanelFieldStateController().wire_combobox_state(combo, cube_state)


def wire_model_picker_state(model_picker: ModelPickerField, cube_state: object) -> None:
    """Bind a model picker through the field-state owner."""

    EditorPanelFieldStateController().wire_model_picker_state(model_picker, cube_state)


def wire_imagepicker_state(imagepicker: ImagePicker, cube_state: object) -> None:
    """Restore an image picker through the field-state owner."""

    EditorPanelFieldStateController().wire_imagepicker_state(imagepicker, cube_state)


__all__ = [
    "bind_node_widget_state",
    "EditorFieldBinding",
    "EditorPanelFieldStateController",
    "EditorPanelFieldStateHost",
    "FieldStateCubeStateProtocol",
    "NODE_STATE_KEYS",
    "set_buffer_value_and_dirty",
    "write_live_widget_value",
    "wire_any_widget_state",
    "wire_combobox_state",
    "wire_imagepicker_state",
    "wire_model_picker_state",
    "wire_prompt_editor_state",
    "wire_widget_state",
]
