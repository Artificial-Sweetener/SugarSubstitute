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

"""Characterize image-field picker selection behavior."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

from pytest import MonkeyPatch

from .support import SignalRecorder


def test_image_picker_emits_when_file_is_selected(monkeypatch: MonkeyPatch) -> None:
    """Update the thumbnail and emit the selected file path."""

    module = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.load_image"
    )
    monkeypatch.setattr(
        module.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: ("C:/images/input.png", "Images"),
    )
    thumbnail_calls: list[str] = []
    selected_signal = SignalRecorder()
    picker = SimpleNamespace(
        default_folder="C:/images",
        _placeholder_image_path=None,
        set_thumbnail=lambda path: thumbnail_calls.append(path),
        imageSelected=selected_signal,
    )

    module.ImagePicker.pick_image(picker)

    assert thumbnail_calls == ["C:/images/input.png"]
    assert selected_signal.calls == [("C:/images/input.png",)]


def test_image_picker_restores_placeholder_when_selection_canceled(
    monkeypatch: MonkeyPatch,
) -> None:
    """Restore the configured placeholder after a cancelled selection."""

    module = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.load_image"
    )
    monkeypatch.setattr(
        module.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: ("", ""),
    )
    placeholder_calls: list[str] = []
    picker = SimpleNamespace(
        default_folder="C:/images",
        _placeholder_image_path="C:/images/default.png",
        set_placeholder_image=lambda path: placeholder_calls.append(path),
    )

    module.ImagePicker.pick_image(picker)

    assert placeholder_calls == ["C:/images/default.png"]


def test_image_picker_current_file_path_returns_internal_value() -> None:
    """Expose the picker's current file-path state."""

    module = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.load_image"
    )
    picker = SimpleNamespace(_current_file_path="C:/images/chosen.png")

    assert module.ImagePicker.current_file_path(picker) == "C:/images/chosen.png"
