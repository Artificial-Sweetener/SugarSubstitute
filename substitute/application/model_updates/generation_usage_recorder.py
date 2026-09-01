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

"""Record exact catalog models referenced by successfully queued generations."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from substitute.application.model_metadata.model_catalog_service import (
    ModelCatalogItem,
)
from sugarsubstitute_shared.model_discovery.models import ModelCategory


class ModelCatalogLookup(Protocol):
    """List enriched Comfy-visible models for one backend kind."""

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return catalog models for one kind."""


class ModelUsageSink(Protocol):
    """Persist one exact model usage event."""

    def record_usage(
        self,
        *,
        sha256: str,
        path: Path,
        category: ModelCategory,
        model_id: int | None,
        version_id: int | None,
        base_model: str | None,
    ) -> object:
        """Record one model reference after successful dispatch."""


class GenerationModelUsageRecorder:
    """Match queued scalar values to exact metadata-backed catalog identities."""

    def __init__(
        self,
        *,
        catalog: ModelCatalogLookup,
        usage: ModelUsageSink,
    ) -> None:
        """Store catalog and authoritative usage boundaries."""

        self._catalog = catalog
        self._usage = usage

    def record_queued_payload(self, workflow_payload: Mapping[str, object]) -> int:
        """Record distinct exact catalog matches and return their count."""

        scalar_values = _scalar_strings(workflow_payload)
        recorded_hashes: set[str] = set()
        for kind, category in _CATEGORIES_BY_KIND.items():
            for item in self._catalog.list_models(kind):
                sha256 = item.sha256
                if (
                    item.backend_value not in scalar_values
                    or sha256 is None
                    or sha256.casefold() in recorded_hashes
                ):
                    continue
                self._usage.record_usage(
                    sha256=sha256,
                    path=Path(item.relative_path),
                    category=category,
                    model_id=_optional_positive_int(item.provider_model_id),
                    version_id=_optional_positive_int(item.provider_model_version_id),
                    base_model=item.base_model,
                )
                recorded_hashes.add(sha256.casefold())
        return len(recorded_hashes)


def _scalar_strings(value: object) -> frozenset[str]:
    """Return nested string scalar values from a compiled workflow payload."""

    values: set[str] = set()
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            values.add(current)
        elif isinstance(current, Mapping):
            pending.extend(current.values())
        elif isinstance(current, (list, tuple)):
            pending.extend(current)
    return frozenset(values)


def _optional_positive_int(value: str | None) -> int | None:
    """Parse positive provider identifiers and reject malformed cache data."""

    if value is None or not value.isdigit():
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None


_CATEGORIES_BY_KIND = {
    "checkpoints": ModelCategory.CHECKPOINTS,
    "diffusion_models": ModelCategory.DIFFUSION_MODELS,
    "loras": ModelCategory.LORAS,
    "vae": ModelCategory.VAE,
    "controlnet": ModelCategory.CONTROLNET,
    "upscale_models": ModelCategory.UPSCALE_MODELS,
}


__all__ = ["GenerationModelUsageRecorder", "ModelCatalogLookup", "ModelUsageSink"]
