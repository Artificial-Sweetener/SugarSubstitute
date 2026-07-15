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

"""Connect picker widgets to editor-panel intent signals."""

from __future__ import annotations

from typing import Any

from substitute.presentation.editor.panel.widgets.fields.load_image import ImagePicker
from substitute.presentation.editor.panel.widgets.fields.load_mask import MaskPicker


def bind_picker_signals(
    widget: Any,
    panel: Any,
    *,
    cube_alias: str | None,
    node_name: str,
) -> None:
    """Connect picker widgets to the editor-panel signals that own UI routing."""

    if isinstance(widget, ImagePicker):
        widget.imageSelected.connect(
            lambda path, alias=cube_alias, name=node_name: panel.inputImageChanged.emit(
                alias, name, path
            )
        )
        widget.imageClicked.connect(
            lambda path, alias=cube_alias, name=node_name: panel.inputImageClicked.emit(
                alias, name, path
            )
        )
        return

    if isinstance(widget, MaskPicker):
        widget.maskSelected.connect(
            lambda alias, name, path: panel.inputMaskChanged.emit(alias, name, path)
        )
        widget.clicked.connect(
            lambda alias, name: panel.inputMaskClicked.emit(alias, name, "")
        )


__all__ = ["bind_picker_signals"]
