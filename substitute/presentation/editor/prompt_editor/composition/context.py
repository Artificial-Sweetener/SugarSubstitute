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

"""Describe shell-owned values available while composing a prompt editor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QWidget

type PromptEditorFillPlaneFactory = Callable[..., QWidget]
"""Create one shell-owned fill plane from its concrete host and surface."""

type PromptEditorResizeHandleFactory = Callable[[Any], QWidget]
"""Create the shell resize handle from its concrete public host."""


@dataclass(frozen=True, slots=True)
class PromptEditorCompositionContext:
    """Carry construction-only values supplied by the live public widget."""

    editor: QWidget
    shell_viewport: QWidget
    autocomplete_limit: int
    autocomplete_minimum_prefix_length: int
    fill_plane_factory: PromptEditorFillPlaneFactory
    resize_handle_factory: PromptEditorResizeHandleFactory
