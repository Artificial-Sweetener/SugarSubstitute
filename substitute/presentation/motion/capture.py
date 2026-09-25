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

"""Capture bounded widget snapshots for structural surface motion."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRectF
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

MAX_TARGET_CAPTURE_PIXELS = 4_000_000
MAX_TARGETS = 24


@dataclass(frozen=True, slots=True)
class CapturedSurface:
    """Retain one visible widget's identity, geometry, and pixels."""

    identity: str
    rect: QRectF
    snapshot: QPixmap
    order: int


@dataclass(frozen=True, slots=True)
class SurfaceCapture:
    """Report one bounded capture result and its retained pixel cost."""

    surfaces: tuple[CapturedSurface, ...]
    pixels: int


def capture_surfaces(
    viewport: QWidget,
    widgets: Sequence[tuple[str, QWidget]],
) -> SurfaceCapture:
    """Capture bounded visible targets in viewport coordinates."""

    surfaces: list[CapturedSurface] = []
    captured_pixels = 0
    for identity, widget in widgets[:MAX_TARGETS]:
        if not isValid(widget) or not widget.isVisible():
            continue
        top_left = widget.mapTo(viewport, QPoint(0, 0))
        rect = QRectF(top_left.x(), top_left.y(), widget.width(), widget.height())
        if not rect.intersects(QRectF(viewport.rect())):
            continue
        pixel_ratio = widget.devicePixelRatioF()
        estimated_pixels = int(
            widget.width() * pixel_ratio * widget.height() * pixel_ratio
        )
        if (
            estimated_pixels <= 0
            or captured_pixels + estimated_pixels > MAX_TARGET_CAPTURE_PIXELS
        ):
            continue
        snapshot = widget.grab()
        if snapshot.isNull():
            continue
        snapshot_pixels = snapshot.width() * snapshot.height()
        if captured_pixels + snapshot_pixels > MAX_TARGET_CAPTURE_PIXELS:
            continue
        captured_pixels += snapshot_pixels
        surfaces.append(
            CapturedSurface(
                identity=identity,
                rect=rect,
                snapshot=snapshot,
                order=len(surfaces),
            )
        )
    return SurfaceCapture(tuple(surfaces), captured_pixels)


def capture_background_without_targets(
    viewport: QWidget,
    widgets: Sequence[tuple[str, QWidget]],
) -> QPixmap:
    """Capture final pixels without duplicating animated live targets."""

    visible_targets = tuple(
        widget
        for _, widget in widgets[:MAX_TARGETS]
        if isValid(widget) and widget.isVisible()
    )
    for widget in visible_targets:
        widget.hide()
    try:
        return viewport.grab()
    finally:
        for widget in visible_targets:
            if isValid(widget):
                widget.show()


__all__ = [
    "CapturedSurface",
    "MAX_TARGET_CAPTURE_PIXELS",
    "MAX_TARGETS",
    "SurfaceCapture",
    "capture_background_without_targets",
    "capture_surfaces",
]
