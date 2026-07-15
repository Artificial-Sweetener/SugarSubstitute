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

"""Expose Comfy infrastructure adapters without eager runtime imports."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.infrastructure.comfy.asset_stagers import (
        LocalComfyAssetStager,
        RemoteUploadComfyAssetStager,
    )
    from substitute.infrastructure.comfy.cube_library_event_listener import (
        CubeLibraryChangedUpdate,
        CubeLibraryEventListener,
    )
    from substitute.infrastructure.comfy.gateway_adapter import (
        InfrastructureComfyGatewayAdapter,
    )
    from substitute.infrastructure.comfy.model_catalog_event_listener import (
        ModelCatalogEventListener,
    )
    from substitute.infrastructure.comfy.prompt_gateway import ComfyPromptGateway

_LAZY_EXPORTS = {
    "ComfyPromptGateway": (
        "substitute.infrastructure.comfy.prompt_gateway",
        "ComfyPromptGateway",
    ),
    "CubeLibraryChangedUpdate": (
        "substitute.infrastructure.comfy.cube_library_event_listener",
        "CubeLibraryChangedUpdate",
    ),
    "CubeLibraryEventListener": (
        "substitute.infrastructure.comfy.cube_library_event_listener",
        "CubeLibraryEventListener",
    ),
    "InfrastructureComfyGatewayAdapter": (
        "substitute.infrastructure.comfy.gateway_adapter",
        "InfrastructureComfyGatewayAdapter",
    ),
    "LocalComfyAssetStager": (
        "substitute.infrastructure.comfy.asset_stagers",
        "LocalComfyAssetStager",
    ),
    "ModelCatalogEventListener": (
        "substitute.infrastructure.comfy.model_catalog_event_listener",
        "ModelCatalogEventListener",
    ),
    "RemoteUploadComfyAssetStager": (
        "substitute.infrastructure.comfy.asset_stagers",
        "RemoteUploadComfyAssetStager",
    ),
}


def __getattr__(name: str) -> object:
    """Load exported Comfy infrastructure adapters on first access."""

    try:
        module_name, attribute_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    from importlib import import_module

    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


__all__ = [
    "ComfyPromptGateway",
    "CubeLibraryChangedUpdate",
    "CubeLibraryEventListener",
    "InfrastructureComfyGatewayAdapter",
    "LocalComfyAssetStager",
    "ModelCatalogEventListener",
    "RemoteUploadComfyAssetStager",
]
