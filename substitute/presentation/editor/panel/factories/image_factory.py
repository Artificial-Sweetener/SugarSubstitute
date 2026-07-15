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

"""Build image and mask picker field widgets from prepared field inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from substitute.application.node_behavior import FieldBehavior, FieldPresentation
from substitute.presentation.editor.panel.widgets.fields.load_image import ImagePicker
from substitute.presentation.editor.panel.widgets.fields.load_mask import MaskPicker


@dataclass(frozen=True, slots=True)
class ImageMaskFieldBuildRequest:
    """Carry prepared image or mask picker field data to the factory."""

    parent: Any
    field_behavior: FieldBehavior
    node_name: str
    key: str
    value: object
    field_meta: dict[str, object]


class ImageMaskFieldFactory:
    """Build passive image and mask picker widgets for picker presentations."""

    def build_field_widget(self, request: ImageMaskFieldBuildRequest) -> object | None:
        """Return an image or mask picker, or None for unrelated presentations."""

        if request.field_behavior.presentation == FieldPresentation.IMAGE_PICKER:
            return build_image_picker_widget(
                request.parent,
                request.node_name,
                request.key,
                request.value,
                request.field_meta,
            )
        if request.field_behavior.presentation == FieldPresentation.MASK_PICKER:
            return build_mask_picker_widget(
                request.parent,
                request.node_name,
                request.key,
                request.value,
                request.field_meta,
            )
        return None


def build_image_picker_widget(
    parent: Any,
    node_name: str,
    key: str,
    value: object,
    field_meta: dict[str, object],
) -> ImagePicker:
    """Build an image picker widget for a behavior-selected field."""

    _ = field_meta
    field = ImagePicker(parent)
    if value:
        field.set_thumbnail(cast(Any, value))
    field.setProperty("input_metadata", {"node_name": node_name, "key": key})
    if not value:
        field.set_thumbnail("")
    return field


def build_mask_picker_widget(
    parent: Any,
    node_name: str,
    key: str,
    value: object,
    field_meta: dict[str, object],
) -> MaskPicker:
    """Build a mask picker widget for a behavior-selected field."""

    cube_alias = field_meta.get("cube_alias")

    field: MaskPicker = cast(Any, MaskPicker)(
        parent=parent,
        cube_alias=cube_alias,
        node_name=node_name,
    )
    if value:
        field.set_mask_path(cast(Any, value))

    field.setProperty(
        "input_metadata",
        {
            "cube_alias": cube_alias,
            "node_name": node_name,
            "key": key,
        },
    )
    if not value:
        field.set_mask_path("")
    return field
