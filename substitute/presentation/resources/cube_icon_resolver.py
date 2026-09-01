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

"""Resolve cube metadata into immediate presentation icons with fallback."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.presentation.resources.app_icon import AppIcon
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.resources.cube_icon_resolver")


class CubeIconFactoryProtocol(Protocol):
    """Resolve cube metadata into a presentation-compatible icon object."""

    def icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
        render_size: int | None = None,
    ) -> object:
        """Return a concrete icon object for one cube surface."""


@dataclass(frozen=True)
class CubeIconResult:
    """Describe the icon selected for one cube presentation surface."""

    icon: object
    used_fallback_icon: bool
    warnings: tuple[str, ...] = ()


class CubeIconResolver:
    """Resolve cube icons while always returning an immediate fallback."""

    def __init__(
        self,
        *,
        cube_icon_factory: CubeIconFactoryProtocol | None,
        fallback_icon: object | None = None,
    ) -> None:
        """Store dependencies for deterministic cube icon resolution."""

        self._cube_icon_factory = cube_icon_factory
        self._fallback_icon = fallback_icon or AppIcon.CUBE_20_FILLED

    def icon_for_cube_state(
        self,
        cube_state: object,
        *,
        workflow_id: str,
        cube_alias: str,
    ) -> CubeIconResult:
        """Return a resolved cube icon or the deterministic fallback icon."""

        cube_id = str(getattr(cube_state, "cube_id", cube_alias))
        display_name = str(getattr(cube_state, "display_name", cube_alias))
        return self.icon_for_cube_source(
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            cube_id=cube_id,
            display_name=display_name,
            icon=_cube_ui_value(cube_state, "cube_icon"),
            catalog_revision=_cube_ui_text(cube_state, "catalog_revision"),
            content_hash=_cube_ui_text(cube_state, "content_hash"),
        )

    def icon_for_cube_source(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str,
        content_hash: str,
    ) -> CubeIconResult:
        """Return a resolved source icon or the deterministic fallback icon."""

        if self._cube_icon_factory is None:
            warning = "missing_cube_icon_factory"
            log_warning(
                _LOGGER,
                "Fell back to default cube icon because factory was missing",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                cube_id=cube_id,
            )
            return CubeIconResult(
                icon=self._fallback_icon,
                used_fallback_icon=True,
                warnings=(warning,),
            )
        try:
            resolved_icon = self._cube_icon_factory.icon_for_cube(
                cube_id=cube_id,
                display_name=display_name,
                icon=icon,
                catalog_revision=catalog_revision,
                cube_content_hash=content_hash,
            )
        except (RuntimeError, TypeError, ValueError) as error:
            warning = "cube_icon_resolution_failed"
            log_warning(
                _LOGGER,
                "Fell back to default cube icon after resolution failure",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                cube_id=cube_id,
                error=repr(error),
            )
            return CubeIconResult(
                icon=self._fallback_icon,
                used_fallback_icon=True,
                warnings=(warning,),
            )
        return CubeIconResult(icon=resolved_icon, used_fallback_icon=False)


def _cube_ui_value(cube_state: object, key: str) -> object | None:
    """Return one cube UI payload value when present."""

    ui_payload = getattr(cube_state, "ui", None)
    return ui_payload.get(key) if isinstance(ui_payload, Mapping) else None


def _cube_ui_text(cube_state: object, key: str) -> str:
    """Return one cube UI payload string when present."""

    value = _cube_ui_value(cube_state, key)
    return value if isinstance(value, str) else ""


__all__ = ["CubeIconFactoryProtocol", "CubeIconResolver", "CubeIconResult"]
