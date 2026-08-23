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

"""Test combobox field-state binding."""

from __future__ import annotations

from pytest import MonkeyPatch

from types import SimpleNamespace


from tests.presentation.editor.panel.field_state.support import (
    _ComboWidget,
    _Signal,
    _SignalMap,
    _as_combo_box,
    _prepare_field_state_module,
    ComboBoxBase,
    field_state_controller,
)


def test_wire_combobox_state_linked_sampler_skips_restore_and_unlinks_on_literal(
    monkeypatch: MonkeyPatch,
) -> None:
    """Linked sampler fields keep UI selection and unlink when switched to literal."""
    _prepare_field_state_module(monkeypatch)
    module = field_state_controller
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

    module.wire_combobox_state(_as_combo_box(combo), cube_state)

    # Restore is intentionally skipped while a link is active.
    assert combo.currentText() == "(linked label)"

    # Switching to a literal value removes the link and writes the buffer.
    combo.currentTextChanged[str].emit("euler")
    assert "sampler_link" not in cube_state.buffer["nodes"]["ksampler"]
    assert cube_state.buffer["nodes"]["ksampler"]["inputs"]["sampler_name"] == "euler"
    assert cube_state.dirty is True


def test_wire_combobox_state_applies_prepared_sampler_link_choices(
    monkeypatch: MonkeyPatch,
) -> None:
    """Prepared sampler link choices should mutate through field-state ownership."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller
    metadata = {"node_name": "ksampler", "key": "sampler_name"}
    combo = _ComboWidget(initial_text="link:A", metadata=metadata)
    setattr(
        combo,
        "_editor_choice_values_by_label",
        {
            "link:A": {"from_cube": "A", "from_node": "ksampler"},
            "heun": "heun",
        },
    )
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

    module.wire_combobox_state(_as_combo_box(combo), cube_state)
    combo.currentTextChanged[str].emit("heun")

    assert cube_state.buffer["nodes"]["ksampler"]["inputs"]["sampler_name"] == "heun"
    assert "sampler_link" not in cube_state.buffer["nodes"]["ksampler"]
    assert cube_state.dirty is True


def test_wire_combobox_state_does_not_normalize_stale_non_link_literal_on_restore(
    monkeypatch: MonkeyPatch,
) -> None:
    """Combobox restore must not mutate stale non-link literals in the underlying buffer."""
    _prepare_field_state_module(monkeypatch)
    module = field_state_controller
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

    module.wire_combobox_state(_as_combo_box(combo), cube_state)

    assert combo.currentText() == "modelA.safetensors"
    assert (
        cube_state.buffer["nodes"]["checkpoint"]["inputs"]["ckpt_name"]
        == "Illustrious  Noobnai3_v9.safetensors"
    )
    assert cube_state.dirty is False


def test_bind_node_widget_state_sets_metadata_for_direct_combobox_widgets(
    monkeypatch: MonkeyPatch,
) -> None:
    """Direct combo widgets should receive input metadata before wiring runs."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _DirectCombo(ComboBoxBase):
        def __init__(self) -> None:
            self._text = ""
            self._props: dict[str, object] = {}
            self._signal = _Signal()
            self.currentTextChanged = _SignalMap(self._signal)

        def property(self, name: str) -> object | None:
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
