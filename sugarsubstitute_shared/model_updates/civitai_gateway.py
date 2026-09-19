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

"""Resolve compatible updates through CivitAI's ordered model-version API."""

from __future__ import annotations

from sugarsubstitute_shared.model_discovery.civitai_client import (
    CivitaiDiscoveryClient,
)
from sugarsubstitute_shared.model_discovery.models import (
    DiscoveredModel,
    ModelArtifactKind,
)


class CivitaiCompatibleUpdateGateway:
    """Offer only safe same-base-model versions published before the current entry."""

    def __init__(self, client: CivitaiDiscoveryClient) -> None:
        """Store the shared authenticated discovery client."""

        self._client = client

    def latest_compatible(
        self,
        *,
        model_id: int,
        current_version_id: int,
        artifact_kind: ModelArtifactKind,
        base_model: str | None,
    ) -> DiscoveredModel | None:
        """Return the newest safe compatible version only when current is observed."""

        candidate: DiscoveredModel | None = None
        for version in self._client.discover_model_versions(
            model_id=model_id,
            artifact_kind=artifact_kind,
        ):
            if version.version_id == current_version_id:
                return candidate
            if candidate is None and _same_base_model(version.base_model, base_model):
                candidate = version
        return None


def _same_base_model(candidate: str | None, current: str | None) -> bool:
    """Fail closed unless provider base-model compatibility is exact."""

    if candidate is None or current is None:
        return False
    return candidate.strip().casefold() == current.strip().casefold()


__all__ = ["CivitaiCompatibleUpdateGateway"]
