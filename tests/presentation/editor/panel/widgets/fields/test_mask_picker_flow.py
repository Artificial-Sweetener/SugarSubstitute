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

"""Characterize mask-field picker selection behavior."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

from pytest import MonkeyPatch

from .support import SignalRecorder


def test_mask_picker_emits_alias_node_and_path(monkeypatch: MonkeyPatch) -> None:
    """Update the mask path and emit cube, node, and selected path."""

    module = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.load_mask"
    )
    monkeypatch.setattr(
        module.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: ("C:/masks/m1.png", "Images"),
    )
    mask_calls: list[str] = []
    selected_signal = SignalRecorder()
    picker = SimpleNamespace(
        default_folder="C:/masks",
        _placeholder_image_path=None,
        cube_alias="CubeA",
        node_name="MaskNode",
        set_mask_path=lambda path: mask_calls.append(path),
        maskSelected=selected_signal,
    )

    module.MaskPicker.pick_mask(picker)

    assert mask_calls == ["C:/masks/m1.png"]
    assert selected_signal.calls == [("CubeA", "MaskNode", "C:/masks/m1.png")]


def test_mask_picker_restores_placeholder_when_canceled(
    monkeypatch: MonkeyPatch,
) -> None:
    """Restore the configured placeholder after a cancelled selection."""

    module = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.load_mask"
    )
    monkeypatch.setattr(
        module.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: ("", ""),
    )
    placeholder_calls: list[str] = []
    picker = SimpleNamespace(
        default_folder="C:/masks",
        _placeholder_image_path="C:/masks/default.png",
        set_placeholder_image=lambda path: placeholder_calls.append(path),
    )

    module.MaskPicker.pick_mask(picker)

    assert placeholder_calls == ["C:/masks/default.png"]


def test_mask_picker_current_file_path_returns_internal_value() -> None:
    """Expose the picker's current file-path state."""

    module = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.load_mask"
    )
    picker = SimpleNamespace(_current_file_path="C:/masks/active.png")

    assert module.MaskPicker.current_file_path(picker) == "C:/masks/active.png"
