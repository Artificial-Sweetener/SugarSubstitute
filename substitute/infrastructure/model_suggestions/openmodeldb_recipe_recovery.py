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

"""Resolve portable upscaler hashes to verified OpenModelDB downloads."""

from __future__ import annotations

import logging

from substitute.application.recipes import RecipeModelDownloadCandidate
from substitute.domain.model_metadata import CivitaiDownloadAccess
from sugarsubstitute_shared.model_acquisition import ModelAcquisitionError
from sugarsubstitute_shared.model_discovery import ModelArtifactKind

from .openmodeldb_catalog import OpenModelDbCatalogClient, OpenModelDbCatalogError
from .openmodeldb_provider import require_openmodeldb_download_url

_LOGGER = logging.getLogger(__name__)


class OpenModelDbRecipeRecoveryGateway:
    """Offer OpenModelDB first for exact portable upscaler hashes."""

    def __init__(self, catalog: OpenModelDbCatalogClient) -> None:
        """Store the governed catalog client."""

        self._catalog = catalog

    def candidate(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> RecipeModelDownloadCandidate | None:
        """Return a direct OpenModelDB candidate for an exact upscaler hash."""

        if kind != ModelArtifactKind.UPSCALE_MODELS.value:
            return None
        normalized_sha256 = sha256.strip().casefold()
        try:
            match = self._catalog.load().resource_for_sha256(normalized_sha256)
        except OpenModelDbCatalogError as error:
            _LOGGER.warning(
                "OpenModelDB portable-model lookup failed",
                extra={"kind": kind, "sha256": normalized_sha256.upper()},
                exc_info=error,
            )
            return None
        if match is None:
            return None
        model, resource = match
        download_url = next(
            (url for url in resource.urls if _is_supported_download_url(url)),
            None,
        )
        if download_url is None:
            return None
        numeric_identity = int(normalized_sha256[:8], 16)
        version_name = " · ".join(
            part
            for part in (
                f"{model.scale}×" if model.scale is not None else None,
                model.architecture.upper() if model.architecture else None,
            )
            if part is not None
        )
        return RecipeModelDownloadCandidate(
            kind=kind,
            sha256=normalized_sha256.upper(),
            name=(
                f"{model.model_id}.{resource.resource_type}"
                if resource.file_name == f"model.{resource.resource_type}"
                else resource.file_name
            ),
            download_url=download_url,
            size_kb=resource.size_bytes / 1024,
            model_id=numeric_identity,
            model_version_id=numeric_identity,
            model_name=model.name,
            version_name=version_name or "Upscaler",
            base_model=None,
            creator=model.author,
            file_id=None,
            file_type="Model",
            metadata_format=(
                "SafeTensor" if resource.resource_type == "safetensors" else "PyTorch"
            ),
            pickle_scan_result=None,
            virus_scan_result=None,
            model_page_url=model.model_page_url,
            thumbnail_url=model.thumbnail_url,
            download_access=CivitaiDownloadAccess.PUBLIC,
            provider_id="openmodeldb",
            provider_name="OpenModelDB",
            size_bytes=resource.size_bytes,
        )


def _is_supported_download_url(url: str) -> bool:
    """Return whether one catalog URL passes the direct-host allowlist."""

    try:
        require_openmodeldb_download_url(url)
    except ModelAcquisitionError:
        return False
    return True


__all__ = ["OpenModelDbRecipeRecoveryGateway"]
