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

"""Tests for panel image and mask field factory ownership."""

from __future__ import annotations

import pytest

from substitute.application.node_behavior import FieldBehavior, FieldPresentation
import substitute.presentation.editor.panel.factories.image_factory as image_factory
from substitute.presentation.editor.panel.factories.image_factory import (
    ImageMaskFieldBuildRequest,
    ImageMaskFieldFactory,
)


class _FakeImagePicker:
    """Record image picker thumbnail state and metadata."""

    def __init__(self, parent: object = None) -> None:
        """Record constructor arguments."""

        self.parent = parent
        self.thumbnail_paths: list[object] = []
        self._properties: dict[str, object] = {}

    def set_thumbnail(self, path: object) -> None:
        """Record assigned thumbnail path."""

        self.thumbnail_paths.append(path)

    def setProperty(self, name: str, value: object) -> None:
        """Set a Qt-style dynamic property."""

        self._properties[name] = value

    def property(self, name: str) -> object | None:
        """Return a Qt-style dynamic property."""

        return self._properties.get(name)


class _FakeMaskPicker:
    """Record mask picker constructor arguments, path state, and metadata."""

    def __init__(
        self,
        *,
        parent: object = None,
        cube_alias: object = None,
        node_name: str = "",
    ) -> None:
        """Record constructor arguments."""

        self.parent = parent
        self.cube_alias = cube_alias
        self.node_name = node_name
        self.mask_paths: list[object] = []
        self._properties: dict[str, object] = {}

    def set_mask_path(self, path: object) -> None:
        """Record assigned mask path."""

        self.mask_paths.append(path)

    def setProperty(self, name: str, value: object) -> None:
        """Set a Qt-style dynamic property."""

        self._properties[name] = value

    def property(self, name: str) -> object | None:
        """Return a Qt-style dynamic property."""

        return self._properties.get(name)


def test_image_factory_builds_image_picker_with_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IMAGE_PICKER fields should build image pickers with selected thumbnails."""

    monkeypatch.setattr(image_factory, "ImagePicker", _FakeImagePicker)

    widget = ImageMaskFieldFactory().build_field_widget(
        ImageMaskFieldBuildRequest(
            parent="parent",
            field_behavior=FieldBehavior(
                field_key="image",
                presentation=FieldPresentation.IMAGE_PICKER,
            ),
            node_name="LoadImage",
            key="image",
            value="E:/images/input.png",
            field_meta={"cube_alias": "A"},
        )
    )

    assert isinstance(widget, _FakeImagePicker)
    assert widget.parent == "parent"
    assert widget.thumbnail_paths == ["E:/images/input.png"]
    assert widget.property("input_metadata") == {
        "node_name": "LoadImage",
        "key": "image",
    }


def test_image_factory_restores_empty_image_picker_thumbnail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty IMAGE_PICKER values should still reset the picker thumbnail."""

    monkeypatch.setattr(image_factory, "ImagePicker", _FakeImagePicker)

    widget = image_factory.build_image_picker_widget(
        parent=None,
        node_name="LoadImage",
        key="image",
        value="",
        field_meta={},
    )

    assert isinstance(widget, _FakeImagePicker)
    assert widget.thumbnail_paths == [""]
    assert widget.property("input_metadata") == {
        "node_name": "LoadImage",
        "key": "image",
    }


def test_image_factory_builds_mask_picker_with_refresh_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MASK_PICKER fields should preserve cube/node metadata used by refresh."""

    monkeypatch.setattr(image_factory, "MaskPicker", _FakeMaskPicker)

    widget = ImageMaskFieldFactory().build_field_widget(
        ImageMaskFieldBuildRequest(
            parent="parent",
            field_behavior=FieldBehavior(
                field_key="image",
                presentation=FieldPresentation.MASK_PICKER,
            ),
            node_name="LoadImageMask",
            key="image",
            value="E:/masks/current.png",
            field_meta={"cube_alias": "Inpaint"},
        )
    )

    assert isinstance(widget, _FakeMaskPicker)
    assert widget.parent == "parent"
    assert widget.cube_alias == "Inpaint"
    assert widget.node_name == "LoadImageMask"
    assert widget.mask_paths == ["E:/masks/current.png"]
    assert widget.property("input_metadata") == {
        "cube_alias": "Inpaint",
        "node_name": "LoadImageMask",
        "key": "image",
    }


def test_image_factory_restores_empty_mask_picker_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty MASK_PICKER values should still reset the picker path."""

    monkeypatch.setattr(image_factory, "MaskPicker", _FakeMaskPicker)

    widget = image_factory.build_mask_picker_widget(
        parent=None,
        node_name="LoadImageMask",
        key="image",
        value=None,
        field_meta={"cube_alias": "Inpaint"},
    )

    assert isinstance(widget, _FakeMaskPicker)
    assert widget.mask_paths == [""]
    assert widget.property("input_metadata") == {
        "cube_alias": "Inpaint",
        "node_name": "LoadImageMask",
        "key": "image",
    }


def test_image_factory_declines_unrelated_presentation() -> None:
    """Non-picker field presentations should be left for later factories."""

    widget = ImageMaskFieldFactory().build_field_widget(
        ImageMaskFieldBuildRequest(
            parent=None,
            field_behavior=FieldBehavior(
                field_key="text",
                presentation=FieldPresentation.STANDARD,
            ),
            node_name="Node",
            key="text",
            value="hello",
            field_meta={},
        )
    )

    assert widget is None
