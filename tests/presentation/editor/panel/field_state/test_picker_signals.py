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

"""Test image and mask picker state and signal wiring."""

from __future__ import annotations

from pytest import MonkeyPatch

from types import SimpleNamespace


from tests.presentation.editor.panel.field_state.support import (
    _Signal,
    _as_image_picker,
    _prepare_field_state_module,
    ImagePickerBase,
    MaskPickerBase,
    field_state_controller,
    widget_wiring,
)


def test_wire_imagepicker_state_restores_thumbnail_without_writing_buffer(
    monkeypatch: MonkeyPatch,
) -> None:
    """ImagePicker writes should route through canvas actions, not widget wiring."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _ImagePicker(ImagePickerBase):
        def __init__(self) -> None:
            self._path = ""
            self.imageSelected = _Signal()
            self._props = {"input_metadata": {"node_name": "load", "key": "image"}}

        def property(self, name: str) -> object | None:
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

    module.wire_imagepicker_state(_as_image_picker(imagepicker), cube_state)
    imagepicker.imageSelected.emit("E:/new.png")

    assert imagepicker.current_file_path() == "E:/old.png"
    assert cube_state.buffer["nodes"]["load"]["inputs"]["image"] == "E:/old.png"
    assert cube_state.dirty is False


def test_bind_picker_signals_routes_image_and_mask_events_to_panel(
    monkeypatch: MonkeyPatch,
) -> None:
    """Picker signal wiring should emit panel-level image and mask intents."""

    _prepare_field_state_module(monkeypatch)
    module = widget_wiring
    panel_events: list[tuple[str, object]] = []

    class _Emitter:
        """Panel signal double that records emitted values."""

        def __init__(self, name: str) -> None:
            """Store signal name."""

            self._name = name

        def emit(self, *args: object) -> None:
            """Record one emission."""

            panel_events.append((self._name, args))

    class _ImagePicker(ImagePickerBase):
        """Image picker double exposing production signals."""

        def __init__(self) -> None:
            """Initialize image picker signals."""

            self.imageSelected = _Signal()
            self.imageClicked = _Signal()

    class _MaskPicker(MaskPickerBase):
        """Mask picker double exposing production signals."""

        def __init__(self) -> None:
            """Initialize mask picker signals."""

            self.maskSelected = _Signal()
            self.clicked = _Signal()
            self.visualOpacityChanged = _Signal()
            self.visualOpacityCommitted = _Signal()

    panel = SimpleNamespace(
        inputImageChanged=_Emitter("image_changed"),
        inputImageClicked=_Emitter("image_clicked"),
        inputMaskChanged=_Emitter("mask_changed"),
        inputMaskClicked=_Emitter("mask_clicked"),
        inputMaskOpacityChanged=_Emitter("mask_opacity"),
        inputMaskOpacityCommitted=_Emitter("mask_opacity_commit"),
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
    mask_picker.visualOpacityChanged.emit("CubeA", "mask_node", 0.37)
    mask_picker.visualOpacityCommitted.emit("CubeA", "mask_node", 0.5, 0.37)

    assert panel_events == [
        ("image_changed", ("CubeA", "image_node", "E:/image.png")),
        ("image_clicked", ("CubeA", "image_node", "E:/image.png")),
        ("mask_changed", ("CubeA", "mask_node", "E:/mask.png")),
        ("mask_clicked", ("CubeA", "mask_node", "")),
        ("mask_opacity", ("CubeA", "mask_node", 0.37)),
        ("mask_opacity_commit", ("CubeA", "mask_node", 0.5, 0.37)),
    ]
