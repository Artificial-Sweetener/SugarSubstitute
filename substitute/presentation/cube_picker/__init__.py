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

"""Presentation widgets for selecting cubes in the workspace."""

from __future__ import annotations

from substitute.presentation.cube_picker.cube_picker_card import CubePickerCard
from substitute.presentation.cube_picker.cube_stack_cart_modal import (
    CubeCatalogRefreshCallback,
    CubePickerClassifyCallback,
    CubePickerDialog,
    CubePickerIconFactoryProtocol,
    CubeStackCartModal,
    CubeStackPickerController,
    CubeStagingDrawer,
)

__all__ = [
    "CubeCatalogRefreshCallback",
    "CubePickerClassifyCallback",
    "CubePickerCard",
    "CubePickerDialog",
    "CubePickerIconFactoryProtocol",
    "CubeStackCartModal",
    "CubeStackPickerController",
    "CubeStagingDrawer",
]
