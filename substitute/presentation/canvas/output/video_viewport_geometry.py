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

"""Map panel-space video navigation onto libmpv's scaled-video coordinates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VideoViewportGeometry:
    """Describe fitted video extents relative to the physical viewport."""

    fitted_width_ratio: float
    fitted_height_ratio: float

    @classmethod
    def create(
        cls,
        *,
        surface_width: int,
        surface_height: int,
        device_pixel_ratio: float,
        source_width: int,
        source_height: int,
    ) -> VideoViewportGeometry:
        """Build geometry from positive surface and decoded-source metrics."""

        physical_width = max(1.0, surface_width * device_pixel_ratio)
        physical_height = max(1.0, surface_height * device_pixel_ratio)
        bounded_source_width = max(1, source_width)
        bounded_source_height = max(1, source_height)
        fit_scale = min(
            physical_width / bounded_source_width,
            physical_height / bounded_source_height,
        )
        return cls(
            fitted_width_ratio=bounded_source_width * fit_scale / physical_width,
            fitted_height_ratio=(bounded_source_height * fit_scale / physical_height),
        )

    def clamp_panel_pan(
        self,
        *,
        zoom: float,
        pan_x: float,
        pan_y: float,
    ) -> tuple[float, float]:
        """Keep a panel-space translation within the scaled video extents."""

        limit_x = max(0.0, self.fitted_width_ratio * zoom - 1.0)
        limit_y = max(0.0, self.fitted_height_ratio * zoom - 1.0)
        return (
            min(limit_x, max(-limit_x, pan_x)),
            min(limit_y, max(-limit_y, pan_y)),
        )

    def mpv_pan(
        self,
        *,
        zoom: float,
        panel_pan_x: float,
        panel_pan_y: float,
    ) -> tuple[float, float]:
        """Convert panel translation into fractions of scaled video size."""

        bounded_zoom = max(zoom, 1.0 / 64.0)
        return (
            panel_pan_x / (2.0 * self.fitted_width_ratio * bounded_zoom),
            panel_pan_y / (2.0 * self.fitted_height_ratio * bounded_zoom),
        )


def viewport_geometry(
    surface_metrics: tuple[int, int, float] | None,
    *,
    source_width: int | None,
    source_height: int | None,
) -> VideoViewportGeometry | None:
    """Create geometry only when both surface and source metrics are available."""

    if surface_metrics is None or source_width is None or source_height is None:
        return None
    surface_width, surface_height, device_pixel_ratio = surface_metrics
    return VideoViewportGeometry.create(
        surface_width=surface_width,
        surface_height=surface_height,
        device_pixel_ratio=device_pixel_ratio,
        source_width=source_width,
        source_height=source_height,
    )


__all__ = ["VideoViewportGeometry", "viewport_geometry"]
