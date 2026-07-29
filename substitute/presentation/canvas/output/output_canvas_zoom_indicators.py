#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Attach the established zoom feedback to each active Output image surface."""

from __future__ import annotations

from PySide6.QtCore import QObject
from cutecanvas import CanvasPresentationKind, CanvasWorkspace, CuteCanvas

from substitute.presentation.canvas.shared.canvas_comparison_zoom_indicator import (
    CanvasComparisonZoomIndicator,
)
from substitute.presentation.canvas.shared.canvas_zoom_indicator import (
    CanvasZoomIndicator,
)


class OutputCanvasZoomIndicators(QObject):
    """Own one standard percentage overlay for every activated Output image."""

    def __init__(self, workspace: CanvasWorkspace) -> None:
        """Observe public workspace changes without depending on Output routes."""

        super().__init__(workspace)
        self._workspace = workspace
        self._indicators: dict[CuteCanvas, CanvasZoomIndicator] = {}
        self._comparison_indicator = CanvasComparisonZoomIndicator(workspace)
        workspace.presentationChanged.connect(self._synchronize)
        workspace.targetActivated.connect(self._synchronize)
        workspace.destroyed.connect(lambda _object=None: self.close())
        self._synchronize()

    def close(self) -> None:
        """Release every attached canvas overlay exactly once."""

        indicators = tuple(self._indicators.values())
        self._indicators.clear()
        self._comparison_indicator.close()
        self._comparison_indicator.deleteLater()
        for indicator in indicators:
            indicator.close()
            indicator.deleteLater()

    def _synchronize(self, _event: object | None = None) -> None:
        """Attach feedback to the currently interactive Output image surface."""

        target = self._active_surface()
        if target is None or target in self._indicators:
            return
        self._indicators[target] = CanvasZoomIndicator(target)
        target.destroyed.connect(
            lambda _object=None, canvas=target: self._release_canvas(canvas)
        )

    def _active_surface(self) -> CuteCanvas | None:
        """Return the sole current interactive surface for the active presentation."""

        presentation = self._workspace.session.presentation
        if presentation.kind in {
            CanvasPresentationKind.GRID,
            CanvasPresentationKind.COMPARISON,
        }:
            return None
        active_composition_id = self._workspace.session.active_composition_id
        return (
            None
            if active_composition_id is None
            else self._workspace.canvasFor(active_composition_id)
        )

    def _release_canvas(self, canvas: CuteCanvas) -> None:
        """Close one overlay after its public canvas is destroyed."""

        indicator = self._indicators.pop(canvas, None)
        if indicator is not None:
            indicator.close()
            indicator.deleteLater()


__all__ = ["OutputCanvasZoomIndicators"]
