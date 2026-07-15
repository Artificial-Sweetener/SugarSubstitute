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

"""Expose packaged application-orb layer resources."""

from __future__ import annotations

from typing import Literal

APP_ORB_RESOURCE_PREFIX = ":/substitute/app/orb"
APP_ORB_LAYER_NAMES: tuple[str, ...] = (
    "orb_base",
    "orb_lower_overlay",
    "orb_upper_overlay",
)

AppOrbLayerName = Literal["orb_base", "orb_lower_overlay", "orb_upper_overlay"]


def app_orb_layer_resource_path(layer_name: AppOrbLayerName) -> str:
    """Return the Qt resource path for one packaged orb layer."""

    if layer_name not in APP_ORB_LAYER_NAMES:
        raise ValueError(f"Unsupported application orb layer: {layer_name}")
    return f"{APP_ORB_RESOURCE_PREFIX}/{layer_name}.png"


def ensure_app_orb_resources_registered() -> None:
    """Import the generated Qt resource module for application-orb layers."""

    from substitute.presentation.resources import app_orb_rc

    _ = app_orb_rc


__all__ = [
    "APP_ORB_LAYER_NAMES",
    "APP_ORB_RESOURCE_PREFIX",
    "AppOrbLayerName",
    "app_orb_layer_resource_path",
    "ensure_app_orb_resources_registered",
]
