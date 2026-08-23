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

"""Test model-picker field-state binding."""

from __future__ import annotations

from pytest import MonkeyPatch

from types import SimpleNamespace


from tests.presentation.editor.panel.field_state.support import (
    _Signal,
    _SignalMap,
    _as_model_picker,
    _prepare_field_state_module,
    ModelPickerFieldBase,
    SeedBoxBase,
    field_state_controller,
)


def test_wire_model_picker_state_restores_and_writes_backend_values(
    monkeypatch: MonkeyPatch,
) -> None:
    """Model picker wiring should restore and persist backend literals only."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _DirectModelPicker(ModelPickerFieldBase):
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

        def property(self, name: str) -> object | None:
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

    module.wire_model_picker_state(_as_model_picker(picker), cube_state)

    assert picker.currentText() == "models/base.safetensors"
    assert cube_state.dirty is False

    picker.setCurrentText("models/next.safetensors")
    picker.currentTextChanged[str].emit("models/next.safetensors")

    assert cube_state.buffer["nodes"]["checkpoint"]["inputs"]["ckpt_name"] == (
        "models/next.safetensors"
    )
    assert cube_state.dirty is True


def test_wire_model_picker_state_keeps_dirty_false_for_same_backend_value(
    monkeypatch: MonkeyPatch,
) -> None:
    """Model picker selection should not dirty the cube when the value is unchanged."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _DirectModelPicker(ModelPickerFieldBase):
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

        def property(self, name: str) -> object | None:
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

    module.wire_model_picker_state(_as_model_picker(picker), cube_state)
    picker.currentTextChanged[str].emit("models/base.safetensors")

    assert cube_state.buffer["nodes"]["checkpoint"]["inputs"]["ckpt_name"] == (
        "models/base.safetensors"
    )
    assert cube_state.dirty is False


def test_bind_node_widget_state_preserves_existing_safe_input_metadata(
    monkeypatch: MonkeyPatch,
) -> None:
    """Existing sanitized widget metadata should not be overwritten during wiring."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _DirectSeedBox(SeedBoxBase):
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

        def property(self, name: str) -> object | None:
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
