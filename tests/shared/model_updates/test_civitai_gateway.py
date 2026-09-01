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

"""Verify fail-closed provider ordering and base-model compatibility."""

from __future__ import annotations

from sugarsubstitute_shared.model_discovery.models import (
    DiscoveredModel,
    ModelCategory,
)
from sugarsubstitute_shared.model_updates.civitai_gateway import (
    CivitaiCompatibleUpdateGateway,
)


class _Client:
    """Return injected safe versions in provider order."""

    def __init__(self, versions: tuple[DiscoveredModel, ...]) -> None:
        """Store versions."""

        self.versions = versions

    def discover_model_versions(self, **_kwargs: object) -> tuple[DiscoveredModel, ...]:
        """Return provider-ordered versions."""

        return self.versions


def _version(identifier: int, base_model: str) -> DiscoveredModel:
    """Build one safe version candidate."""

    return DiscoveredModel(
        category=ModelCategory.CHECKPOINTS,
        model_id=1,
        version_id=identifier,
        model_name="Model",
        version_name=f"v{identifier}",
        creator=None,
        base_model=base_model,
        file_name=f"v{identifier}.safetensors",
        size_bytes=1,
        sha256=f"{identifier:x}" * 64,
        download_url=f"https://civitai.com/api/download/models/{identifier}",
        model_page_url="https://civitai.com/models/1",
        thumbnail_url=None,
        provider_rank=1,
    )


def test_gateway_selects_newest_compatible_version_before_current() -> None:
    """Provider ordering should yield the first exact-base version before current."""

    gateway = CivitaiCompatibleUpdateGateway(
        _Client((_version(4, "Flux"), _version(3, "SDXL"), _version(2, "SDXL")))  # type: ignore[arg-type]
    )

    candidate = gateway.latest_compatible(
        model_id=1,
        current_version_id=2,
        category=ModelCategory.CHECKPOINTS,
        base_model="sdxl",
    )

    assert candidate is not None
    assert candidate.version_id == 3


def test_gateway_returns_none_when_current_version_is_not_observed() -> None:
    """Missing current-version evidence must not turn an older entry into an update."""

    gateway = CivitaiCompatibleUpdateGateway(
        _Client((_version(4, "SDXL"), _version(3, "SDXL")))  # type: ignore[arg-type]
    )

    assert (
        gateway.latest_compatible(
            model_id=1,
            current_version_id=2,
            category=ModelCategory.CHECKPOINTS,
            base_model="SDXL",
        )
        is None
    )
