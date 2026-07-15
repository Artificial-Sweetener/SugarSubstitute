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

"""Expose shared domain errors and value-object aliases."""

from __future__ import annotations

from substitute.domain.common.errors import (
    DomainError,
    StackPolicyError,
    WorkflowStateError,
)
from substitute.domain.common.value_objects import (
    CubeAlias,
    CubeBaseName,
    FieldKey,
    GlobalOverrideMap,
    GlobalOverrideSelectionMap,
    GlobalOverrideValue,
    ImageIdentity,
    ImageToMaskMap,
    InputImageMap,
    InputKey,
    JsonObject,
    JsonPrimitive,
    JsonValue,
    MaskAssociationKey,
    MaskAssociationMap,
    MaskToImageMap,
    NodeName,
    WorkflowId,
)

__all__ = [
    "CubeAlias",
    "CubeBaseName",
    "DomainError",
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
    "StackPolicyError",
    "WorkflowId",
    "WorkflowStateError",
]
