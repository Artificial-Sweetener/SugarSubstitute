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

"""Defer construction of the optional CivitAI HTTP metadata adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from substitute.application.model_metadata import CivitaiMetadataGateway
    from substitute.domain.model_metadata import (
        CivitaiDownloadAccess,
        CivitaiLookupResult,
    )


class LazyCivitaiClient:
    """Construct and cache the concrete CivitAI client on first use."""

    def __init__(self, *, api_key_provider: Callable[[], str | None]) -> None:
        """Store the secure API-key provider without reading it eagerly."""

        self._api_key_provider = api_key_provider
        self._client: CivitaiMetadataGateway | None = None

    def lookup_model_version_by_hash(self, sha256: str) -> CivitaiLookupResult:
        """Look up CivitAI metadata through the lazily created client."""

        return self._resolve().lookup_model_version_by_hash(sha256)

    def model_version_download_access(
        self,
        model_version_id: int,
    ) -> CivitaiDownloadAccess:
        """Return download access without eagerly reading stored credentials."""

        lookup = getattr(self._resolve(), "model_version_download_access")
        return cast("CivitaiDownloadAccess", lookup(model_version_id))

    def _resolve(self) -> CivitaiMetadataGateway:
        """Build and cache the concrete CivitAI client."""

        if self._client is None:
            from substitute.infrastructure.external.civitai_client import (
                CivitaiClient,
            )

            self._client = CivitaiClient(api_key_provider=self._api_key_provider)
        return self._client


__all__ = ["LazyCivitaiClient"]
