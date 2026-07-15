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

"""Characterization tests for image/mask picker selection flows."""

from __future__ import annotations

import importlib
from types import SimpleNamespace


class _Signal:
    """Signal recorder."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def emit(self, *args) -> None:
        """Record emitted arguments."""
        self.calls.append(args)


def test_image_picker_pick_image_emits_when_file_is_selected(monkeypatch) -> None:
    """Image picker should update thumbnail and emit selected file path."""
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.load_image"
    )
    monkeypatch.setattr(
        mod.QFileDialog,
        "getOpenFileName",
        lambda *_a, **_k: ("C:/images/input.png", "Images"),
    )
    thumbnail_calls: list[str] = []
    selected_signal = _Signal()
    fake = SimpleNamespace(
        default_folder="C:/images",
        _placeholder_image_path=None,
        set_thumbnail=lambda path: thumbnail_calls.append(path),
        imageSelected=selected_signal,
    )

    mod.ImagePicker.pick_image(fake)

    assert thumbnail_calls == ["C:/images/input.png"]
    assert selected_signal.calls == [("C:/images/input.png",)]


def test_image_picker_pick_image_restores_placeholder_when_selection_canceled(
    monkeypatch,
) -> None:
    """Cancel path with placeholder should restore placeholder thumbnail."""
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.load_image"
    )
    monkeypatch.setattr(mod.QFileDialog, "getOpenFileName", lambda *_a, **_k: ("", ""))
    placeholder_calls: list[str] = []
    fake = SimpleNamespace(
        default_folder="C:/images",
        _placeholder_image_path="C:/images/default.png",
        set_placeholder_image=lambda path: placeholder_calls.append(path),
    )

    mod.ImagePicker.pick_image(fake)

    assert placeholder_calls == ["C:/images/default.png"]


def test_image_picker_current_file_path_returns_internal_value() -> None:
    """current_file_path returns the picker's current path state."""
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.load_image"
    )
    fake = SimpleNamespace(_current_file_path="C:/images/chosen.png")

    assert mod.ImagePicker.current_file_path(fake) == "C:/images/chosen.png"


def test_mask_picker_pick_mask_emits_alias_node_and_path(monkeypatch) -> None:
    """Mask picker should emit cube alias, node name, and selected path."""
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.load_mask"
    )
    monkeypatch.setattr(
        mod.QFileDialog,
        "getOpenFileName",
        lambda *_a, **_k: ("C:/masks/m1.png", "Images"),
    )
    mask_calls: list[str] = []
    selected_signal = _Signal()
    fake = SimpleNamespace(
        default_folder="C:/masks",
        _placeholder_image_path=None,
        cube_alias="CubeA",
        node_name="MaskNode",
        set_mask_path=lambda path: mask_calls.append(path),
        maskSelected=selected_signal,
    )

    mod.MaskPicker.pick_mask(fake)

    assert mask_calls == ["C:/masks/m1.png"]
    assert selected_signal.calls == [("CubeA", "MaskNode", "C:/masks/m1.png")]


def test_mask_picker_pick_mask_restores_placeholder_when_canceled(monkeypatch) -> None:
    """Cancel path with placeholder should restore placeholder image."""
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.load_mask"
    )
    monkeypatch.setattr(mod.QFileDialog, "getOpenFileName", lambda *_a, **_k: ("", ""))
    placeholder_calls: list[str] = []
    fake = SimpleNamespace(
        default_folder="C:/masks",
        _placeholder_image_path="C:/masks/default.png",
        set_placeholder_image=lambda path: placeholder_calls.append(path),
    )

    mod.MaskPicker.pick_mask(fake)

    assert placeholder_calls == ["C:/masks/default.png"]


def test_mask_picker_current_file_path_returns_internal_value() -> None:
    """current_file_path returns current mask path state."""
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.load_mask"
    )
    fake = SimpleNamespace(_current_file_path="C:/masks/active.png")

    assert mod.MaskPicker.current_file_path(fake) == "C:/masks/active.png"
