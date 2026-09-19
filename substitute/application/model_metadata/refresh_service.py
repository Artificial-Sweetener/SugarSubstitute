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

"""Coordinate startup model metadata enrichment and cache updates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import time

from substitute.application.model_metadata.ports import (
    BackendModelMetadataGateway,
    CivitaiMetadataGateway,
    ModelMetadataCatalogRepository,
    ModelMetadataProgressSink,
    ModelThumbnailRepository,
    RefreshCancellationToken,
)
from substitute.application.civitai import CivitaiPreferenceService
from substitute.domain.model_metadata import (
    BackendCapabilities,
    BackendModelCatalogEntry,
)
from substitute.domain.model_metadata.thumbnail_policy import (
    CivitaiThumbnailPolicy,
)
from substitute.shared.logging.logger import get_logger

from .fingerprint_refresh import ModelFingerprintRefresh
from .metadata_enrichment import ModelMetadataEnrichmentService
from .refresh_summary import ModelMetadataRefreshSummary

_LOGGER = get_logger("application.model_metadata.refresh_service")
DEFAULT_MODEL_KINDS = (
    "checkpoints",
    "loras",
    "vae",
    "embeddings",
    "controlnet",
    "hypernetworks",
    "upscale_models",
    "diffusion_models",
)


class ModelMetadataRefreshService:
    """Refresh CivitAI metadata for Comfy-visible models."""

    def __init__(
        self,
        *,
        backend: BackendModelMetadataGateway,
        civitai: CivitaiMetadataGateway,
        catalog: ModelMetadataCatalogRepository,
        thumbnails: ModelThumbnailRepository,
        thumbnail_policy: CivitaiThumbnailPolicy | None = None,
        civitai_preferences: CivitaiPreferenceService | None = None,
        clock: Callable[[], str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        model_kinds: tuple[str, ...] = DEFAULT_MODEL_KINDS,
        capability_wait_timeout_seconds: float = 20.0,
        capability_retry_interval_seconds: float = 0.5,
        fingerprint_poll_interval_seconds: float = 0.5,
    ) -> None:
        """Initialize the refresh service with its application ports."""

        self._backend = backend
        self._enrichment = ModelMetadataEnrichmentService(
            civitai=civitai,
            catalog=catalog,
            thumbnails=thumbnails,
            thumbnail_policy=thumbnail_policy,
            civitai_preferences=civitai_preferences,
            clock=clock,
        )
        self._fingerprints = ModelFingerprintRefresh(
            backend,
            sleep=sleep,
            poll_interval_seconds=fingerprint_poll_interval_seconds,
        )
        self._sleep = sleep
        self._model_kinds = model_kinds
        self._capability_wait_timeout_seconds = capability_wait_timeout_seconds
        self._capability_retry_interval_seconds = capability_retry_interval_seconds

    def refresh(
        self,
        progress: ModelMetadataProgressSink,
        *,
        cancellation_token: RefreshCancellationToken,
    ) -> ModelMetadataRefreshSummary:
        """Run one metadata refresh and report user-visible progress."""

        cancellation = cancellation_token
        progress.emit_line("Model metadata: checking backend capabilities.")
        capabilities = self._wait_for_capabilities(progress, cancellation)
        if capabilities is None or not capabilities.background_hashing:
            progress.emit_line(
                "Model metadata: Substitute BackEnd model API unavailable; skipping startup metadata refresh."
            )
            return ModelMetadataRefreshSummary()

        supported_kinds = tuple(
            kind
            for kind in self._model_kinds
            if kind in capabilities.supported_model_kinds
        )
        if not supported_kinds:
            progress.emit_line(
                "Model metadata: backend reports no supported model kinds."
            )
            return ModelMetadataRefreshSummary()

        models = self._backend.list_models(supported_kinds)
        progress.emit_line(
            f"Model metadata: found {len(models)} Comfy models across {len(supported_kinds)} kinds."
        )
        if cancellation.is_cancelled():
            progress.emit_line("Model metadata: refresh canceled during shutdown.")
            return ModelMetadataRefreshSummary(discovered=len(models), cancelled=True)

        complete_summary = self.refresh_entries(
            models,
            progress,
            cancellation_token=cancellation,
        )
        if complete_summary.cancelled:
            progress.emit_line("Model metadata: refresh canceled during shutdown.")
            return complete_summary
        progress.emit_line(
            (
                "Model metadata: incomplete. "
                if complete_summary.failed
                else "Model metadata: complete. "
            )
            + f"{complete_summary.enriched} metadata records updated, "
            f"{complete_summary.thumbnails_cached} thumbnails cached, "
            f"{complete_summary.not_found} not found, "
            f"{complete_summary.skipped} skipped, {complete_summary.failed} failed."
        )
        return complete_summary

    def refresh_entries(
        self,
        models: tuple[BackendModelCatalogEntry, ...],
        progress: ModelMetadataProgressSink,
        *,
        cancellation_token: RefreshCancellationToken,
    ) -> ModelMetadataRefreshSummary:
        """Refresh CivitAI metadata for a scoped set of backend catalog entries."""

        total = ModelMetadataRefreshSummary(discovered=len(models))
        for batch in self._fingerprints.batches(models, progress, cancellation_token):
            result = self._enrichment.enrich(
                models=batch.models,
                refreshed_hashes={
                    (kind, value): sha for kind, value, sha in batch.hashes
                },
                progress=progress,
                cancellation=cancellation_token,
            )
            total = ModelMetadataRefreshSummary(
                discovered=total.discovered,
                fingerprint_requested=total.fingerprint_requested + batch.requested,
                enriched=total.enriched + result.enriched,
                thumbnails_cached=total.thumbnails_cached + result.thumbnails_cached,
                not_found=total.not_found + result.not_found,
                skipped=total.skipped + result.skipped,
                no_sfw_thumbnail=total.no_sfw_thumbnail + result.no_sfw_thumbnail,
                failed=total.failed + result.failed + batch.failed,
                cancelled=result.cancelled,
            )
        return replace(
            total, cancelled=total.cancelled or cancellation_token.is_cancelled()
        )

    def _wait_for_capabilities(
        self,
        progress: ModelMetadataProgressSink,
        cancellation: RefreshCancellationToken,
    ) -> BackendCapabilities | None:
        """Poll backend capabilities after Comfy starts accepting connections."""

        deadline = time.monotonic() + self._capability_wait_timeout_seconds
        first_retry = True
        while not cancellation.is_cancelled():
            capabilities = self._backend.get_capabilities()
            if capabilities is not None:
                return capabilities
            if time.monotonic() >= deadline:
                return None
            if first_retry:
                progress.emit_line(
                    "Model metadata: waiting for Substitute BackEnd model API."
                )
                first_retry = False
            else:
                progress.emit_progress(
                    "Model metadata: waiting for Substitute BackEnd model API\r"
                )
            self._sleep(self._capability_retry_interval_seconds)
        return None


__all__ = ["DEFAULT_MODEL_KINDS", "ModelMetadataRefreshService"]
