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

"""Project Input editor geometry into contextual-toolbar placement."""

from __future__ import annotations

from cutecanvas import EditorTransformTarget, FloatingPixelSnapshot

from substitute.presentation.canvas.shared.contextual_toolbar import (
    CanvasContextualToolbar,
    ContextualToolbarPlacementUpdate,
)

from .input_tool_options_contracts import InputToolOptionsDocumentPort


class InputContextualToolbarPlacement:
    """Own mapping from Input editor snapshots to toolbar context bounds."""

    def __init__(
        self,
        *,
        document: InputToolOptionsDocumentPort,
        toolbar: CanvasContextualToolbar,
    ) -> None:
        """Bind the public geometry adapter and presentation target."""

        self._document = document
        self._toolbar = toolbar

    def update_selection(
        self,
        update: ContextualToolbarPlacementUpdate,
        *,
        retain_when_missing: bool = False,
    ) -> None:
        """Place the toolbar from current selection bounds."""

        bounds = self._document.pixel_selection_panel_bounds()
        if bounds is None and retain_when_missing:
            return
        self._toolbar.set_context_rect(bounds, update=update)

    def update_transform(
        self,
        target: EditorTransformTarget,
        update: ContextualToolbarPlacementUpdate,
    ) -> None:
        """Place the toolbar from one live affine target frame."""

        bounds = self._document.transform_panel_bounds(target)
        if bounds is not None:
            self._toolbar.set_context_rect(bounds, update=update)

    def update_floating(
        self,
        state: FloatingPixelSnapshot | None,
        update: ContextualToolbarPlacementUpdate,
    ) -> None:
        """Place floating pixels or fall back to their selection boundary."""

        bounds = (
            None if state is None else self._document.floating_pixel_panel_bounds(state)
        )
        if bounds is None:
            self.update_selection(update)
            return
        self._toolbar.set_context_rect(bounds, update=update)


__all__ = ["InputContextualToolbarPlacement"]
