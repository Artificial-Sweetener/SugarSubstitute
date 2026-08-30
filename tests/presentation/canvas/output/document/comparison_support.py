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

"""Provide shared Output document fixtures and observations."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID
from PySide6.QtCore import QLineF, QPointF
from PySide6.QtGui import (
    QColor,
)
from PySide6.QtWidgets import QApplication, QWidget
from cutecanvas import (
    ComparisonOrientation,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _ZoomModeProbe(Protocol):
    """Describe the zoom-mode value exposed by a native comparison viewport."""

    value: str


class _ViewportProbe(Protocol):
    """Describe renderer-neutral viewport observations used by the fixture."""

    def get_zoom_mode(self) -> _ZoomModeProbe:
        """Return the active zoom interpretation."""

    def computeFitZoom(self) -> float:  # noqa: N802
        """Return the fit scale for the mounted comparison."""

    def setZoomAndPan(self, zoom: float, pan: QPointF) -> None:  # noqa: N802
        """Apply an exact mounted comparison viewport."""


class _CatalogEntryProbe(Protocol):
    """Describe one catalog entry used to verify the presented pair."""

    entry_id: UUID


class _CatalogProbe(Protocol):
    """Describe catalog state observable through the native test surface."""

    entries: tuple[_CatalogEntryProbe, ...]
    current: _CatalogEntryProbe | None


class _ComparisonStateProbe(Protocol):
    """Describe comparison state observable through the native test surface."""

    source_id: UUID | None
    split_position: float
    orientation: ComparisonOrientation


class _LinkedGroupProbe(Protocol):
    """Describe one renderer-neutral linked inspection group."""

    members: tuple[UUID, ...]


class _DividerStateProbe(Protocol):
    """Describe mounted divider geometry needed by interaction tests."""

    enabled: bool
    dragging: bool
    full_segment: QLineF | None
    visible_segment: QLineF | None


class _NativeComparisonProbe(Protocol):
    """Describe comparison observations without importing the QPane renderer."""

    viewport: _ViewportProbe

    def catalog(self) -> _CatalogProbe:
        """Return the mounted comparison catalog."""

    def comparisonState(self) -> _ComparisonStateProbe:  # noqa: N802
        """Return the mounted comparison state."""

    def linkedImageGroups(self) -> tuple[_LinkedGroupProbe, ...]:  # noqa: N802
        """Return renderer-neutral linked inspection groups."""

    def applyZoom(self, requested_zoom: float) -> None:  # noqa: N802
        """Apply one exact comparison zoom."""

    def currentZoom(self) -> float:  # noqa: N802
        """Return the mounted comparison zoom."""

    def currentPan(self) -> QPointF:  # noqa: N802
        """Return the mounted comparison pan."""

    def comparisonDividerState(self) -> _DividerStateProbe:  # noqa: N802
        """Return mounted divider geometry."""

    def setZoomFit(self) -> None:  # noqa: N802
        """Fit the mounted comparison."""


def _wait_for_comparison_colors(
    application: QApplication,
    target: QWidget,
    *,
    primary: QColor,
    secondary: QColor,
) -> bool:
    """Wait until one native reveal pane renders both admitted source colors."""

    del application

    def comparison_colors_match() -> bool:
        """Compare current quarter samples with both expected colors."""

        image = target.grab().toImage()
        if image.isNull():
            return False
        left = image.pixelColor(image.width() // 4, image.height() // 2)
        right = image.pixelColor(3 * image.width() // 4, image.height() // 2)
        return left == primary and right == secondary

    wait_for_qt_condition(comparison_colors_match)
    return True
