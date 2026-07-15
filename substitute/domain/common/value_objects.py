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

"""Define shared domain value objects for workflow state and policy modules."""

from __future__ import annotations

from typing import TypeAlias
from uuid import UUID

WorkflowId: TypeAlias = str
CubeAlias: TypeAlias = str
CubeBaseName: TypeAlias = str
NodeName: TypeAlias = str
FieldKey: TypeAlias = str
InputKey: TypeAlias = str

MaskAssociationKey: TypeAlias = tuple[CubeAlias, NodeName]
ImageIdentity: TypeAlias = tuple[CubeAlias, NodeName]

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = object
JsonObject: TypeAlias = dict[str, JsonValue]

GlobalOverrideValue: TypeAlias = dict[str, JsonValue]
GlobalOverrideMap: TypeAlias = dict[FieldKey, GlobalOverrideValue]
GlobalOverrideSelectionMap: TypeAlias = dict[FieldKey, bool]

InputImageMap: TypeAlias = dict[InputKey, UUID]
MaskAssociationMap: TypeAlias = dict[MaskAssociationKey, UUID]
ImageToMaskMap: TypeAlias = dict[ImageIdentity, list[MaskAssociationKey]]
MaskToImageMap: TypeAlias = dict[UUID, UUID]

__all__ = [
    "CubeAlias",
    "CubeBaseName",
    "FieldKey",
    "GlobalOverrideMap",
    "GlobalOverrideSelectionMap",
    "GlobalOverrideValue",
    "ImageIdentity",
    "ImageToMaskMap",
    "InputImageMap",
    "InputKey",
    "JsonObject",
    "JsonPrimitive",
    "JsonValue",
    "MaskAssociationKey",
    "MaskAssociationMap",
    "MaskToImageMap",
    "NodeName",
    "WorkflowId",
]
