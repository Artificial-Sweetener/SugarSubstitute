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

"""Acquire OpenModelDB portable-workflow models into standard Comfy folders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.recipes import RecipeModelDownloadCandidate
from substitute.domain.model_metadata import (
    BackendModelDownloadJob,
    ModelDownloadStatus,
)
from sugarsubstitute_shared.model_acquisition import (
    AcquisitionProgress,
    ModelAcquisitionService,
)
from sugarsubstitute_shared.model_discovery import (
    DiscoveredModel,
    ModelArtifactDestinationPolicy,
    ModelArtifactKind,
)


@dataclass(frozen=True, slots=True)
class _CallableCancellationProbe:
    """Adapt a recipe cancellation callback to model acquisition semantics."""

    callback: Callable[[], bool] | None

    def is_cancelled(self) -> bool:
        """Return whether the owning recipe flow requested cancellation."""

        return False if self.callback is None else self.callback()


class OpenModelDbRecipeAcquirer:
    """Download exact OpenModelDB artifacts for portable workflow recovery."""

    def __init__(
        self,
        *,
        acquisition: ModelAcquisitionService,
        destinations: ModelArtifactDestinationPolicy,
    ) -> None:
        """Store verified transfer and standard destination policies."""

        self._acquisition = acquisition
        self._destinations = destinations

    def acquire(
        self,
        candidate: RecipeModelDownloadCandidate,
        *,
        progress_callback: Callable[[BackendModelDownloadJob], None] | None,
        should_cancel: Callable[[], bool] | None,
    ) -> str:
        """Acquire an exact resource and return its Comfy-visible relative value."""

        if candidate.provider_id != "openmodeldb" or candidate.size_bytes is None:
            raise ValueError("OpenModelDB candidate metadata is incomplete.")
        artifact_kind = ModelArtifactKind(candidate.kind)
        destination = self._destinations.destination_for(artifact_kind)
        job_id = f"openmodeldb-{candidate.sha256[:12].casefold()}"

        def publish(progress: AcquisitionProgress) -> None:
            """Project byte progress into the existing model-download presentation."""

            if progress_callback is not None:
                progress_callback(
                    BackendModelDownloadJob(
                        job_id=job_id,
                        status=ModelDownloadStatus.RUNNING,
                        kind=candidate.kind,
                        sha256=candidate.sha256,
                        value=None,
                        result=None,
                        error=None,
                        bytes_downloaded=progress.bytes_received,
                        bytes_total=progress.expected_bytes,
                        detail=candidate.provider_name,
                    )
                )

        result = self._acquisition.acquire(
            DiscoveredModel(
                artifact_kind=artifact_kind,
                model_id=candidate.model_id,
                version_id=candidate.model_version_id,
                model_name=candidate.model_name,
                version_name=candidate.version_name,
                creator=candidate.creator,
                base_model=candidate.base_model,
                file_name=candidate.name,
                size_bytes=candidate.size_bytes,
                sha256=candidate.sha256,
                download_url=candidate.download_url,
                model_page_url=candidate.model_page_url,
                thumbnail_url=candidate.thumbnail_url,
                provider_rank=1,
            ),
            destination_dir=destination,
            cancellation=_CallableCancellationProbe(should_cancel),
            on_progress=publish,
        )
        value = result.path.relative_to(destination).as_posix()
        if progress_callback is not None:
            progress_callback(
                BackendModelDownloadJob(
                    job_id=job_id,
                    status=ModelDownloadStatus.COMPLETE,
                    kind=candidate.kind,
                    sha256=result.sha256,
                    value=value,
                    result=None,
                    error=None,
                    bytes_downloaded=result.size_bytes,
                    bytes_total=result.size_bytes,
                    detail=candidate.provider_name,
                )
            )
        return value


__all__ = ["OpenModelDbRecipeAcquirer"]
