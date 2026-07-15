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

"""Expose external integration adapters without eager client imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.infrastructure.external.civitai_client import CivitaiClient
    from substitute.infrastructure.external.comfy_object_info_client import (
        ComfyObjectInfoClient,
    )
    from substitute.infrastructure.external.danbooru_client import DanbooruClient
    from substitute.infrastructure.external.photoshop_gateway import PhotoshopGateway
    from substitute.infrastructure.external.native_file_manager_gateway import (
        NativeFileManagerGateway,
    )
    from substitute.infrastructure.external.substitute_backend_cube_icon_asset_client import (
        SubstituteBackendCubeIconAssetClient,
    )
    from substitute.infrastructure.external.substitute_backend_cube_library_client import (
        SubstituteBackendCubeLibraryClient,
    )
    from substitute.infrastructure.external.substitute_backend_environment_client import (
        SubstituteBackendEnvironmentClient,
    )
    from substitute.infrastructure.external.substitute_backend_model_metadata_client import (
        SubstituteBackendModelMetadataClient,
    )
    from substitute.infrastructure.external.substitute_backend_preview_assets_client import (
        SubstituteBackendPreviewAssetsClient,
    )
    from substitute.infrastructure.external.substitute_backend_sugar_compile_client import (
        BackendSugarCompileError,
        BackendSugarWorkflowPayloadCompiler,
        SubstituteBackendSugarCompileClient,
    )

_LAZY_EXPORTS = {
    "BackendSugarCompileError": (
        "substitute.infrastructure.external.substitute_backend_sugar_compile_client"
    ),
    "BackendSugarWorkflowPayloadCompiler": (
        "substitute.infrastructure.external.substitute_backend_sugar_compile_client"
    ),
    "CivitaiClient": "substitute.infrastructure.external.civitai_client",
    "ComfyObjectInfoClient": (
        "substitute.infrastructure.external.comfy_object_info_client"
    ),
    "DanbooruClient": "substitute.infrastructure.external.danbooru_client",
    "PhotoshopGateway": "substitute.infrastructure.external.photoshop_gateway",
    "NativeFileManagerGateway": (
        "substitute.infrastructure.external.native_file_manager_gateway"
    ),
    "SubstituteBackendCubeLibraryClient": (
        "substitute.infrastructure.external.substitute_backend_cube_library_client"
    ),
    "SubstituteBackendCubeIconAssetClient": (
        "substitute.infrastructure.external.substitute_backend_cube_icon_asset_client"
    ),
    "SubstituteBackendEnvironmentClient": (
        "substitute.infrastructure.external.substitute_backend_environment_client"
    ),
    "SubstituteBackendModelMetadataClient": (
        "substitute.infrastructure.external.substitute_backend_model_metadata_client"
    ),
    "SubstituteBackendPreviewAssetsClient": (
        "substitute.infrastructure.external.substitute_backend_preview_assets_client"
    ),
    "SubstituteBackendSugarCompileClient": (
        "substitute.infrastructure.external.substitute_backend_sugar_compile_client"
    ),
}


def __getattr__(name: str) -> object:
    """Load one external integration export on first access."""

    try:
        module_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = [
    "BackendSugarCompileError",
    "BackendSugarWorkflowPayloadCompiler",
    "CivitaiClient",
    "ComfyObjectInfoClient",
    "DanbooruClient",
    "PhotoshopGateway",
    "NativeFileManagerGateway",
    "SubstituteBackendCubeLibraryClient",
    "SubstituteBackendCubeIconAssetClient",
    "SubstituteBackendEnvironmentClient",
    "SubstituteBackendModelMetadataClient",
    "SubstituteBackendPreviewAssetsClient",
    "SubstituteBackendSugarCompileClient",
]
