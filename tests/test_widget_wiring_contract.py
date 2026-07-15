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

"""Characterization tests for widget wiring and dirty-state behavior."""

from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace


class _Signal:
    """Tiny signal helper with Qt-like connect/emit."""

    def __init__(self) -> None:
        self._slots = []

    def connect(self, slot) -> None:
        """Register callback."""
        self._slots.append(slot)

    def emit(self, *args, **kwargs) -> None:
        """Emit to callbacks."""
        for slot in list(self._slots):
            slot(*args, **kwargs)


class _SignalMap:
    """Signal map supporting Qt syntax like signal[str].connect(...)."""

    def __init__(self, signal: _Signal) -> None:
        self._signal = signal

    def __getitem__(self, _key):
        """Return underlying signal regardless of key."""
        return self._signal


class _ComboWidget:
    """Minimal combo-like widget used by wire_combobox_state tests."""

    def __init__(
        self,
        initial_text: str,
        metadata: dict,
        *,
        options: list[str] | None = None,
        strict_unknown_text: bool = False,
    ) -> None:
        self._text = initial_text
        self._options = list(options or [])
        self._strict_unknown_text = strict_unknown_text
        self._props = {"input_metadata": metadata}
        self._signal = _Signal()
        self.currentTextChanged = _SignalMap(self._signal)

    def property(self, name: str):
        """Read custom property."""
        return self._props.get(name)

    def currentText(self) -> str:
        """Return current display text."""
        return self._text

    def setCurrentText(self, value: str) -> None:
        """Set current display text."""
        if self._strict_unknown_text and self._options and value not in self._options:
            return
        self._text = value


def _import_widget_wiring_with_stubs(monkeypatch):
    """Import widget_wiring with lightweight dependency stubs for deterministic tests."""
    qfw = sys.modules.get("qfluentwidgets")
    if qfw is None:
        qfw = types.ModuleType("qfluentwidgets")
        sys.modules["qfluentwidgets"] = qfw
    if not hasattr(qfw, "CheckBox"):
        qfw.CheckBox = type("CheckBox", (), {})
    if not hasattr(qfw, "LineEdit"):
        qfw.LineEdit = type("LineEdit", (), {})

    widgets_pkg = types.ModuleType("substitute.presentation.widgets")
    widgets_pkg.ComboBox = type("ComboBox", (), {})
    widgets_pkg.SpinBox = type("SpinBox", (), {})
    widgets_pkg.DoubleSpinBox = type("DoubleSpinBox", (), {})
    widgets_pkg.SeedBox = type("SeedBox", (), {})
    widgets_pkg.__path__ = []
    combo_mod = types.ModuleType("substitute.presentation.widgets.combo_box")
    combo_mod.ComboBox = widgets_pkg.ComboBox
    spin_mod = types.ModuleType("substitute.presentation.widgets.spin_box")
    spin_mod.SpinBox = widgets_pkg.SpinBox
    spin_mod.DoubleSpinBox = widgets_pkg.DoubleSpinBox
    seed_mod = types.ModuleType("substitute.presentation.widgets.seed_box")
    seed_mod.SeedBox = widgets_pkg.SeedBox
    model_picker_mod = types.ModuleType("substitute.presentation.widgets.model_picker")
    model_picker_mod.ModelPickerField = type("ModelPickerField", (), {})
    prompt_mod = types.ModuleType("substitute.presentation.editor.prompt_editor")
    prompt_mod.PromptEditor = type("PromptEditor", (), {})
    image_mod = types.ModuleType(
        "substitute.presentation.editor.panel.widgets.fields.load_image"
    )
    image_mod.ImagePicker = type("ImagePicker", (), {})
    mask_mod = types.ModuleType(
        "substitute.presentation.editor.panel.widgets.fields.load_mask"
    )
    mask_mod.MaskPicker = type("MaskPicker", (), {})

    monkeypatch.setitem(sys.modules, "substitute.presentation.widgets", widgets_pkg)
    monkeypatch.setitem(
        sys.modules, "substitute.presentation.widgets.combo_box", combo_mod
    )
    monkeypatch.setitem(
        sys.modules, "substitute.presentation.widgets.spin_box", spin_mod
    )
    monkeypatch.setitem(
        sys.modules, "substitute.presentation.widgets.seed_box", seed_mod
    )
    monkeypatch.setitem(
        sys.modules, "substitute.presentation.widgets.model_picker", model_picker_mod
    )
    monkeypatch.setitem(
        sys.modules, "substitute.presentation.editor.prompt_editor", prompt_mod
    )
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.editor.panel.widgets.fields.load_image",
        image_mod,
    )
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.editor.panel.widgets.fields.load_mask",
        mask_mod,
    )

    module = importlib.import_module(
        "substitute.presentation.editor.panel.field_state_controller"
    )
    return importlib.reload(module)


def test_set_buffer_value_and_dirty_respects_node_state_keys(monkeypatch) -> None:
    """Node-state keys write to node root, not to inputs."""
    module = _import_widget_wiring_with_stubs(monkeypatch)
    cube_state = SimpleNamespace(
        buffer={"nodes": {"node": {"enabled": True, "inputs": {"steps": 20}}}},
        dirty=False,
    )

    module.set_buffer_value_and_dirty(cube_state, "node", "enabled", False)

    assert cube_state.buffer["nodes"]["node"]["enabled"] is False
    assert cube_state.buffer["nodes"]["node"]["inputs"]["steps"] == 20
    assert cube_state.dirty is True


def test_wire_widget_state_restores_buffer_value_and_writes_on_change(
    monkeypatch,
) -> None:
    """Generic wiring restores from buffer and marks dirty on changed value."""
    module = _import_widget_wiring_with_stubs(monkeypatch)

    signal = _Signal()
    widget = SimpleNamespace(
        value=0,
        _props={"input_metadata": {"node_name": "node", "key": "steps"}},
    )
    widget.property = lambda name: widget._props.get(name)
    cube_state = SimpleNamespace(
        buffer={"nodes": {"node": {"inputs": {"steps": 10}}}},
        dirty=False,
    )

    module.wire_widget_state(
        widget,
        cube_state,
        get_val_func=lambda w: w.value,
        set_val_func=lambda w, v: setattr(w, "value", v),
        signal=signal,
    )

    assert widget.value == 10
    signal.emit(12)
    assert cube_state.buffer["nodes"]["node"]["inputs"]["steps"] == 12
    assert cube_state.dirty is True


def test_wire_widget_state_keeps_dirty_false_for_unchanged_value(monkeypatch) -> None:
    """Generic widget writes should not dirty the cube when the value is unchanged."""

    module = _import_widget_wiring_with_stubs(monkeypatch)
    signal = _Signal()
    widget = SimpleNamespace(
        value=10,
        _props={"input_metadata": {"node_name": "node", "key": "steps"}},
    )
    widget.property = lambda name: widget._props.get(name)
    cube_state = SimpleNamespace(
        buffer={"nodes": {"node": {"inputs": {"steps": 10}}}},
        dirty=False,
    )

    module.wire_widget_state(
        widget,
        cube_state,
        get_val_func=lambda w: w.value,
        set_val_func=lambda w, v: setattr(w, "value", v),
        signal=signal,
    )
    signal.emit(10)

    assert cube_state.buffer["nodes"]["node"]["inputs"]["steps"] == 10
    assert cube_state.dirty is False


def test_wire_widget_state_prefers_resolved_display_fallback_for_initial_restore(
    monkeypatch,
) -> None:
    """Live fallback displays should not be overwritten by raw blank buffer values."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    signal = _Signal()
    widget = SimpleNamespace(
        value=0,
        _props={
            "input_metadata": {
                "node_name": "node",
                "key": "steps",
                "resolved_value": 0,
                "value_source": "live_default",
            }
        },
    )
    widget.property = lambda name: widget._props.get(name)
    cube_state = SimpleNamespace(
        buffer={"nodes": {"node": {"inputs": {"steps": ""}}}},
        dirty=False,
    )

    module.wire_widget_state(
        widget,
        cube_state,
        get_val_func=lambda w: w.value,
        set_val_func=lambda w, v: setattr(w, "value", v),
        signal=signal,
    )

    assert widget.value == 0
    assert cube_state.buffer["nodes"]["node"]["inputs"]["steps"] == ""
    assert cube_state.dirty is False


def test_wire_imagepicker_state_restores_thumbnail_without_writing_buffer(
    monkeypatch,
) -> None:
    """ImagePicker writes should route through canvas actions, not widget wiring."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _ImagePicker(module.ImagePicker):  # type: ignore[misc]
        def __init__(self) -> None:
            self._path = ""
            self.imageSelected = _Signal()
            self._props = {"input_metadata": {"node_name": "load", "key": "image"}}

        def property(self, name: str):
            return self._props.get(name)

        def current_file_path(self) -> str:
            return self._path

        def set_thumbnail(self, path: str) -> None:
            self._path = path

    imagepicker = _ImagePicker()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"load": {"inputs": {"image": "E:/old.png"}}}},
        dirty=False,
    )

    module.wire_imagepicker_state(imagepicker, cube_state)
    imagepicker.imageSelected.emit("E:/new.png")

    assert imagepicker.current_file_path() == "E:/old.png"
    assert cube_state.buffer["nodes"]["load"]["inputs"]["image"] == "E:/old.png"
    assert cube_state.dirty is False


def test_bind_picker_signals_routes_image_and_mask_events_to_panel(monkeypatch) -> None:
    """Picker signal wiring should emit panel-level image and mask intents."""

    _import_widget_wiring_with_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.editor.panel.factories.widget_wiring"
    )
    module = importlib.reload(module)
    panel_events: list[tuple[str, object]] = []

    class _Emitter:
        """Panel signal double that records emitted values."""

        def __init__(self, name: str) -> None:
            """Store signal name."""

            self._name = name

        def emit(self, *args: object) -> None:
            """Record one emission."""

            panel_events.append((self._name, args))

    class _ImagePicker(module.ImagePicker):  # type: ignore[misc]
        """Image picker double exposing production signals."""

        def __init__(self) -> None:
            """Initialize image picker signals."""

            self.imageSelected = _Signal()
            self.imageClicked = _Signal()

    class _MaskPicker(module.MaskPicker):  # type: ignore[misc]
        """Mask picker double exposing production signals."""

        def __init__(self) -> None:
            """Initialize mask picker signals."""

            self.maskSelected = _Signal()
            self.clicked = _Signal()

    panel = SimpleNamespace(
        inputImageChanged=_Emitter("image_changed"),
        inputImageClicked=_Emitter("image_clicked"),
        inputMaskChanged=_Emitter("mask_changed"),
        inputMaskClicked=_Emitter("mask_clicked"),
    )
    image_picker = _ImagePicker()
    mask_picker = _MaskPicker()

    module.bind_picker_signals(
        image_picker,
        panel,
        cube_alias="CubeA",
        node_name="image_node",
    )
    module.bind_picker_signals(
        mask_picker,
        panel,
        cube_alias="CubeA",
        node_name="mask_node",
    )
    image_picker.imageSelected.emit("E:/image.png")
    image_picker.imageClicked.emit("E:/image.png")
    mask_picker.maskSelected.emit("CubeA", "mask_node", "E:/mask.png")
    mask_picker.clicked.emit("CubeA", "mask_node")

    assert panel_events == [
        ("image_changed", ("CubeA", "image_node", "E:/image.png")),
        ("image_clicked", ("CubeA", "image_node", "E:/image.png")),
        ("mask_changed", ("CubeA", "mask_node", "E:/mask.png")),
        ("mask_clicked", ("CubeA", "mask_node", "")),
    ]


def test_wire_combobox_state_linked_sampler_skips_restore_and_unlinks_on_literal(
    monkeypatch,
) -> None:
    """Linked sampler fields keep UI selection and unlink when switched to literal."""
    module = _import_widget_wiring_with_stubs(monkeypatch)
    metadata = {"node_name": "ksampler", "key": "sampler_name"}
    combo = _ComboWidget(initial_text="(linked label)", metadata=metadata)
    cube_state = SimpleNamespace(
        buffer={
            "nodes": {
                "ksampler": {
                    "inputs": {"sampler_name": "from-buffer"},
                    "sampler_link": {"from_cube": "A", "from_node": "ksampler"},
                }
            }
        },
        dirty=False,
    )

    module.wire_combobox_state(combo, cube_state)

    # Restore is intentionally skipped while a link is active.
    assert combo.currentText() == "(linked label)"

    # Switching to a literal value removes the link and writes the buffer.
    combo.currentTextChanged[str].emit("euler")
    assert "sampler_link" not in cube_state.buffer["nodes"]["ksampler"]
    assert cube_state.buffer["nodes"]["ksampler"]["inputs"]["sampler_name"] == "euler"
    assert cube_state.dirty is True


def test_wire_combobox_state_applies_prepared_sampler_link_choices(
    monkeypatch,
) -> None:
    """Prepared sampler link choices should mutate through field-state ownership."""

    module = _import_widget_wiring_with_stubs(monkeypatch)
    metadata = {"node_name": "ksampler", "key": "sampler_name"}
    combo = _ComboWidget(initial_text="link:A", metadata=metadata)
    combo._editor_choice_values_by_label = {
        "link:A": {"from_cube": "A", "from_node": "ksampler"},
        "heun": "heun",
    }
    cube_state = SimpleNamespace(
        buffer={
            "nodes": {
                "ksampler": {
                    "inputs": {"sampler_name": "euler"},
                    "sampler_link": {"from_cube": "A", "from_node": "ksampler"},
                }
            }
        },
        dirty=False,
    )

    module.wire_combobox_state(combo, cube_state)
    combo.currentTextChanged[str].emit("heun")

    assert cube_state.buffer["nodes"]["ksampler"]["inputs"]["sampler_name"] == "heun"
    assert "sampler_link" not in cube_state.buffer["nodes"]["ksampler"]
    assert cube_state.dirty is True


def test_wire_combobox_state_does_not_normalize_stale_non_link_literal_on_restore(
    monkeypatch,
) -> None:
    """Combobox restore must not mutate stale non-link literals in the underlying buffer."""
    module = _import_widget_wiring_with_stubs(monkeypatch)
    metadata = {"node_name": "checkpoint", "key": "ckpt_name"}
    combo = _ComboWidget(
        initial_text="modelA.safetensors",
        metadata=metadata,
        options=["modelA.safetensors", "modelB.safetensors"],
        strict_unknown_text=True,
    )
    cube_state = SimpleNamespace(
        buffer={
            "nodes": {
                "checkpoint": {
                    "inputs": {"ckpt_name": "Illustrious  Noobnai3_v9.safetensors"},
                }
            }
        },
        dirty=False,
    )

    module.wire_combobox_state(combo, cube_state)

    assert combo.currentText() == "modelA.safetensors"
    assert (
        cube_state.buffer["nodes"]["checkpoint"]["inputs"]["ckpt_name"]
        == "Illustrious  Noobnai3_v9.safetensors"
    )
    assert cube_state.dirty is False


def test_bind_node_widget_state_sets_metadata_for_direct_combobox_widgets(
    monkeypatch,
) -> None:
    """Direct combo widgets should receive input metadata before wiring runs."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _DirectCombo(module.ComboBox):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = ""
            self._props: dict[str, object] = {}
            self._signal = _Signal()
            self.currentTextChanged = _SignalMap(self._signal)

        def property(self, name: str):
            return self._props.get(name)

        def setProperty(self, name: str, value: object) -> None:
            self._props[name] = value

        def currentText(self) -> str:
            return self._text

        def setCurrentText(self, value: str) -> None:
            self._text = value

    combo = _DirectCombo()
    cube_state = SimpleNamespace(
        buffer={"nodes": {None: {"inputs": {"scheduler": "normal"}}}},
        dirty=False,
    )

    module.bind_node_widget_state(
        combo,
        cube_state,
        {"node_name": None, "key": "scheduler"},
    )

    assert combo.property("input_metadata") == {"node_name": None, "key": "scheduler"}
    assert combo.currentText() == "normal"

    combo.currentTextChanged[str].emit("karras")

    assert cube_state.buffer["nodes"][None]["inputs"]["scheduler"] == "karras"
    assert cube_state.dirty is True


def test_wire_model_picker_state_restores_and_writes_backend_values(
    monkeypatch,
) -> None:
    """Model picker wiring should restore and persist backend literals only."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _DirectModelPicker(module.ModelPickerField):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = "ui-default.safetensors"
            self._props = {
                "input_metadata": {
                    "node_name": "checkpoint",
                    "key": "ckpt_name",
                }
            }
            self._signal = _Signal()
            self.currentTextChanged = _SignalMap(self._signal)

        def property(self, name: str):
            return self._props.get(name)

        def currentText(self) -> str:
            return self._text

        def setCurrentText(self, value: str) -> None:
            self._text = value

    picker = _DirectModelPicker()
    cube_state = SimpleNamespace(
        buffer={
            "nodes": {
                "checkpoint": {
                    "inputs": {"ckpt_name": "models/base.safetensors"},
                }
            }
        },
        dirty=False,
    )

    module.wire_model_picker_state(picker, cube_state)

    assert picker.currentText() == "models/base.safetensors"
    assert cube_state.dirty is False

    picker.setCurrentText("models/next.safetensors")
    picker.currentTextChanged[str].emit("models/next.safetensors")

    assert cube_state.buffer["nodes"]["checkpoint"]["inputs"]["ckpt_name"] == (
        "models/next.safetensors"
    )
    assert cube_state.dirty is True


def test_wire_model_picker_state_keeps_dirty_false_for_same_backend_value(
    monkeypatch,
) -> None:
    """Model picker selection should not dirty the cube when the value is unchanged."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _DirectModelPicker(module.ModelPickerField):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = "models/base.safetensors"
            self._props = {
                "input_metadata": {
                    "node_name": "checkpoint",
                    "key": "ckpt_name",
                }
            }
            self._signal = _Signal()
            self.currentTextChanged = _SignalMap(self._signal)

        def property(self, name: str):
            return self._props.get(name)

        def currentText(self) -> str:
            return self._text

        def setCurrentText(self, value: str) -> None:
            self._text = value

    picker = _DirectModelPicker()
    cube_state = SimpleNamespace(
        buffer={
            "nodes": {
                "checkpoint": {
                    "inputs": {"ckpt_name": "models/base.safetensors"},
                }
            }
        },
        dirty=False,
    )

    module.wire_model_picker_state(picker, cube_state)
    picker.currentTextChanged[str].emit("models/base.safetensors")

    assert cube_state.buffer["nodes"]["checkpoint"]["inputs"]["ckpt_name"] == (
        "models/base.safetensors"
    )
    assert cube_state.dirty is False


def test_bind_node_widget_state_preserves_existing_safe_input_metadata(
    monkeypatch,
) -> None:
    """Existing sanitized widget metadata should not be overwritten during wiring."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _DirectSeedBox(module.SeedBox):  # type: ignore[misc]
        def __init__(self) -> None:
            self._value = 0
            self._props: dict[str, object] = {
                "input_metadata": {
                    "cube_alias": "A",
                    "node_name": "ksampler",
                    "key": "seed",
                }
            }
            self.valueChanged = _Signal()

        def property(self, name: str):
            return self._props.get(name)

        def setProperty(self, name: str, value: object) -> None:
            self._props[name] = value

        def value(self) -> int:
            return self._value

        def setValue(self, value: int) -> None:
            self._value = value

    seedbox = _DirectSeedBox()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"ksampler": {"inputs": {"seed": 123}}}},
        dirty=False,
    )

    module.bind_node_widget_state(
        seedbox,
        cube_state,
        {
            "cube_alias": "A",
            "node_name": "ksampler",
            "key": "seed",
            "meta_info": {"huge_value": 18446744073709551615},
        },
    )

    assert seedbox.property("input_metadata") == {
        "cube_alias": "A",
        "node_name": "ksampler",
        "key": "seed",
    }
    assert seedbox.value() == 123


def test_bind_node_widget_state_restores_and_persists_prompt_editor_buffer_values(
    monkeypatch,
) -> None:
    """Prompt widgets should restore from the buffer and mark dirty only on real edits."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _DirectPromptEditor(module.PromptEditor):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = "ui-default"
            self._props: dict[str, object] = {}
            self.baseline_source_text_calls: list[str] = []
            self.textChanged = _Signal()

        def property(self, name: str):
            return self._props.get(name)

        def setProperty(self, name: str, value: object) -> None:
            self._props[name] = value

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def replaceBaselineSourceText(self, value: str) -> None:
            """Record authoritative buffer restores through the baseline API."""

            self.baseline_source_text_calls.append(value)
            self._text = value

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
    )

    module.bind_node_widget_state(
        prompt_editor,
        cube_state,
        {"node_name": "positive_prompt", "key": "text"},
    )

    assert prompt_editor.property("input_metadata") == {
        "node_name": "positive_prompt",
        "key": "text",
    }
    assert prompt_editor.toPlainText() == "from-buffer"
    assert prompt_editor.baseline_source_text_calls == ["from-buffer"]
    assert cube_state.dirty is False

    prompt_editor.setPlainText("from-buffer")
    prompt_editor.textChanged.emit()
    assert cube_state.buffer["nodes"]["positive_prompt"]["inputs"]["text"] == (
        "from-buffer"
    )
    assert cube_state.dirty is False

    prompt_editor.setPlainText("updated prompt")
    prompt_editor.textChanged.emit()
    assert cube_state.buffer["nodes"]["positive_prompt"]["inputs"]["text"] == (
        "updated prompt"
    )
    assert cube_state.dirty is True


def test_bind_node_widget_state_restores_prompt_editor_manual_height(
    monkeypatch,
) -> None:
    """Prompt widget wiring should apply stored manual height without dirtying restore."""

    module = _import_widget_wiring_with_stubs(monkeypatch)
    monkeypatch.setattr(
        module,
        "QTimer",
        SimpleNamespace(singleShot=lambda _delay, callback: callback()),
    )

    class _DirectPromptEditor(module.PromptEditor):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = ""
            self._manual_height: int | None = None
            self._props: dict[str, object] = {}
            self.textChanged = _Signal()
            self.manualScrollHeightChanged = _Signal()

        def property(self, name: str):
            return self._props.get(name)

        def setProperty(self, name: str, value: object) -> None:
            self._props[name] = value

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setManualScrollHeight(self, height: int | None) -> None:
            self._manual_height = height
            self.manualScrollHeightChanged.emit(height)

        def manualScrollHeight(self) -> int | None:
            return self._manual_height

    prompt_editor = _DirectPromptEditor()
    autosaves: list[str] = []
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui={
            "prompt_editor_manual_heights": {
                "positive_prompt.text": 260,
            }
        },
    )

    module.bind_node_widget_state(
        prompt_editor,
        cube_state,
        {"node_name": "positive_prompt", "key": "text"},
        manual_prompt_height_changed=lambda: autosaves.append("autosave"),
    )

    assert prompt_editor.manualScrollHeight() == 260
    assert cube_state.dirty is False
    assert autosaves == []


def test_prompt_editor_manual_height_changes_update_cube_ui_and_autosave(
    monkeypatch,
) -> None:
    """Manual prompt height changes should persist under cube UI metadata."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _DirectPromptEditor(module.PromptEditor):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = "from-buffer"
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()
            self.manualScrollHeightChanged = _Signal()

        def property(self, name: str):
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setManualScrollHeight(self, height: int | None) -> None:
            self.manualScrollHeightChanged.emit(height)

    prompt_editor = _DirectPromptEditor()
    autosaves: list[str] = []
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui=None,
    )

    module.wire_prompt_editor_state(
        prompt_editor,
        cube_state,
        manual_height_changed=lambda: autosaves.append("autosave"),
    )
    prompt_editor.setManualScrollHeight(300)

    assert cube_state.ui == {
        "prompt_editor_manual_heights": {
            "positive_prompt.text": 300,
        }
    }
    assert cube_state.dirty is True
    assert autosaves == ["autosave"]


def test_prompt_editor_manual_height_clearing_removes_cube_ui_entry(
    monkeypatch,
) -> None:
    """Clearing manual prompt height should remove the field-specific UI value."""

    module = _import_widget_wiring_with_stubs(monkeypatch)
    monkeypatch.setattr(
        module,
        "QTimer",
        SimpleNamespace(singleShot=lambda _delay, callback: callback()),
    )

    class _DirectPromptEditor(module.PromptEditor):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = "from-buffer"
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()
            self.manualScrollHeightChanged = _Signal()

        def property(self, name: str):
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui={
            "prompt_editor_manual_heights": {
                "positive_prompt.text": 300,
            }
        },
    )

    module.wire_prompt_editor_state(prompt_editor, cube_state)
    prompt_editor.manualScrollHeightChanged.emit(None)

    assert cube_state.ui == {}
    assert cube_state.dirty is True


def test_prompt_editor_invalid_stored_manual_height_is_ignored(
    monkeypatch,
) -> None:
    """Invalid persisted manual height values should not affect the prompt editor."""

    module = _import_widget_wiring_with_stubs(monkeypatch)
    monkeypatch.setattr(
        module,
        "QTimer",
        SimpleNamespace(singleShot=lambda _delay, callback: callback()),
    )

    class _DirectPromptEditor(module.PromptEditor):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = ""
            self._manual_height: int | None = None
            self._props: dict[str, object] = {}
            self.textChanged = _Signal()
            self.manualScrollHeightChanged = _Signal()

        def property(self, name: str):
            return self._props.get(name)

        def setProperty(self, name: str, value: object) -> None:
            self._props[name] = value

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setManualScrollHeight(self, height: int | None) -> None:
            self._manual_height = height
            self.manualScrollHeightChanged.emit(height)

        def manualScrollHeight(self) -> int | None:
            return self._manual_height

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui={
            "prompt_editor_manual_heights": {
                "positive_prompt.text": "tall",
            }
        },
    )

    module.bind_node_widget_state(
        prompt_editor,
        cube_state,
        {"node_name": "positive_prompt", "key": "text"},
    )

    assert prompt_editor.manualScrollHeight() is None
    assert cube_state.dirty is False


def test_prompt_editor_missing_rich_rendering_state_keeps_default_enabled(
    monkeypatch,
) -> None:
    """Missing prompt rich-rendering UI metadata should keep the default enabled state."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _DirectPromptEditor(module.PromptEditor):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = ""
            self._rich_enabled = True
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()
            self.richPromptRenderingEnabledChanged = _Signal()

        def property(self, name: str):
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setSourceText(self, value: str) -> None:
            self._text = value

        def richPromptRenderingEnabled(self) -> bool:
            return self._rich_enabled

        def setRichPromptRenderingEnabled(self, enabled: bool) -> None:
            self._rich_enabled = enabled
            self.richPromptRenderingEnabledChanged.emit(enabled)

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui={},
    )

    module.wire_prompt_editor_state(prompt_editor, cube_state)

    assert prompt_editor.richPromptRenderingEnabled() is True
    assert cube_state.dirty is False


def test_prompt_editor_restores_disabled_rich_rendering_without_dirtying(
    monkeypatch,
) -> None:
    """Stored false rich-rendering preference should restore as raw mode state."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _DirectPromptEditor(module.PromptEditor):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = ""
            self._rich_enabled = True
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()
            self.richPromptRenderingEnabledChanged = _Signal()

        def property(self, name: str):
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setSourceText(self, value: str) -> None:
            self._text = value

        def richPromptRenderingEnabled(self) -> bool:
            return self._rich_enabled

        def setRichPromptRenderingEnabled(self, enabled: bool) -> None:
            self._rich_enabled = enabled
            self.richPromptRenderingEnabledChanged.emit(enabled)

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui={
            "prompt_editor_rich_rendering": {
                "positive_prompt.text": False,
            }
        },
    )

    module.wire_prompt_editor_state(prompt_editor, cube_state)

    assert prompt_editor.richPromptRenderingEnabled() is False
    assert cube_state.dirty is False


def test_prompt_editor_invalid_rich_rendering_state_is_ignored(
    monkeypatch,
) -> None:
    """Invalid rich-rendering UI metadata should not affect prompt editor restore."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _DirectPromptEditor(module.PromptEditor):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = ""
            self._rich_enabled = True
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()
            self.richPromptRenderingEnabledChanged = _Signal()

        def property(self, name: str):
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setSourceText(self, value: str) -> None:
            self._text = value

        def richPromptRenderingEnabled(self) -> bool:
            return self._rich_enabled

        def setRichPromptRenderingEnabled(self, enabled: bool) -> None:
            self._rich_enabled = enabled
            self.richPromptRenderingEnabledChanged.emit(enabled)

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui={
            "prompt_editor_rich_rendering": {
                "positive_prompt.text": "sometimes",
            }
        },
    )

    module.wire_prompt_editor_state(prompt_editor, cube_state)

    assert prompt_editor.richPromptRenderingEnabled() is True
    assert cube_state.dirty is False


def test_prompt_editor_rich_rendering_changes_update_cube_ui_and_autosave(
    monkeypatch,
) -> None:
    """Prompt rich-rendering changes should persist under cube UI metadata."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _DirectPromptEditor(module.PromptEditor):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = "from-buffer"
            self._rich_enabled = True
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()
            self.richPromptRenderingEnabledChanged = _Signal()

        def property(self, name: str):
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setSourceText(self, value: str) -> None:
            self._text = value

        def setRichPromptRenderingEnabled(self, enabled: bool) -> None:
            self._rich_enabled = enabled
            self.richPromptRenderingEnabledChanged.emit(enabled)

    prompt_editor = _DirectPromptEditor()
    autosaves: list[str] = []
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui=None,
    )

    module.wire_prompt_editor_state(
        prompt_editor,
        cube_state,
        manual_height_changed=lambda: autosaves.append("autosave"),
    )
    prompt_editor.setRichPromptRenderingEnabled(False)

    assert cube_state.ui == {
        "prompt_editor_rich_rendering": {
            "positive_prompt.text": False,
        }
    }
    assert cube_state.dirty is True
    assert autosaves == ["autosave"]

    cube_state.dirty = False
    prompt_editor.setRichPromptRenderingEnabled(True)

    assert cube_state.ui == {}
    assert cube_state.dirty is True
    assert autosaves == ["autosave", "autosave"]


def test_wire_any_widget_state_uses_direct_prompt_editor_type_dispatch(
    monkeypatch,
) -> None:
    """Generic wiring should recognize PromptEditor via its concrete type, not a string check."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _DirectPromptEditor(module.PromptEditor):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = "ui-default"
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()

        def property(self, name: str):
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
    )

    module.wire_any_widget_state(prompt_editor, cube_state)

    assert prompt_editor.toPlainText() == "from-buffer"

    prompt_editor.setPlainText("updated prompt")
    prompt_editor.textChanged.emit()

    assert cube_state.buffer["nodes"]["positive_prompt"]["inputs"]["text"] == (
        "updated prompt"
    )
    assert cube_state.dirty is True


def test_bind_node_widget_state_preserves_escaped_prompt_source_verbatim(
    monkeypatch,
) -> None:
    """Prompt widget wiring should restore and persist escaped source text unchanged."""

    module = _import_widget_wiring_with_stubs(monkeypatch)

    class _DirectPromptEditor(module.PromptEditor):  # type: ignore[misc]
        def __init__(self) -> None:
            self._text = ""
            self._props: dict[str, object] = {}
            self.textChanged = _Signal()

        def property(self, name: str):
            return self._props.get(name)

        def setProperty(self, name: str, value: object) -> None:
            self._props[name] = value

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={
            "nodes": {"positive_prompt": {"inputs": {"text": r"painting \(medium\)"}}}
        },
        dirty=False,
    )

    module.bind_node_widget_state(
        prompt_editor,
        cube_state,
        {"node_name": "positive_prompt", "key": "text"},
    )

    assert prompt_editor.toPlainText() == r"painting \(medium\)"

    prompt_editor.setPlainText(r"vertin \(reverse:1999\)")
    prompt_editor.textChanged.emit()

    assert cube_state.buffer["nodes"]["positive_prompt"]["inputs"]["text"] == (
        r"vertin \(reverse:1999\)"
    )
    assert cube_state.dirty is True
