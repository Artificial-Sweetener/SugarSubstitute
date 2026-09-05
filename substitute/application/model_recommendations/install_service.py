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

"""Plan and acquire complete runnable model-family recipes."""

from __future__ import annotations

from collections.abc import Callable, Collection
from pathlib import Path
import shutil
from typing import Protocol

from sugarsubstitute_shared.model_acquisition import (
    AcquisitionProgress,
    AcquisitionResult,
    CancellationProbe,
    ModelAcquisitionService,
)
from sugarsubstitute_shared.model_discovery import DiscoveredModel

from substitute.domain.model_recommendations import (
    ModelInstallFile,
    ModelInstallPlan,
    ModelInstallProgress,
    ModelInstallSource,
    ModelRecipeRole,
    ModelRecommendation,
    SUPPORTED_MODEL_FAMILIES,
    SupportedModelFamilyCatalog,
)


class DiskSpaceProvider(Protocol):
    """Return free bytes for one destination root."""

    def __call__(self, path: Path) -> int:
        """Return current free storage bytes."""


ModelInstallProgressCallback = Callable[[ModelInstallProgress], None]


class ModelInstallRecipePlanner:
    """Expand selected primary models into complete family-owned recipes."""

    def __init__(
        self,
        *,
        catalog: SupportedModelFamilyCatalog = SUPPORTED_MODEL_FAMILIES,
        free_space: DiskSpaceProvider | None = None,
    ) -> None:
        """Store the family catalog and review-time disk-space boundary."""

        self._catalog = catalog
        self._free_space = free_space or _free_space

    def plan(
        self,
        recommendations: Collection[ModelRecommendation],
        *,
        model_root: Path,
    ) -> ModelInstallPlan:
        """Return exact primary and deduplicated auxiliary files for review."""

        root = model_root.resolve(strict=False)
        files: list[ModelInstallFile] = []
        auxiliary_identities: set[tuple[str, str]] = set()
        for recommendation in recommendations:
            family = self._catalog.get(recommendation.family_id)
            files.append(
                ModelInstallFile(
                    family_id=recommendation.family_id,
                    role=ModelRecipeRole.PRIMARY_MODEL,
                    artifact_kind=family.primary_artifact_kind,
                    source=ModelInstallSource.CIVITAI,
                    model_id=recommendation.model_id,
                    version_id=recommendation.version_id,
                    display_name=recommendation.model_name,
                    file_name=recommendation.file_name,
                    source_url=recommendation.download_url,
                    sha256=recommendation.sha256,
                    size_bytes=recommendation.size_bytes,
                    destination_dir=root / family.primary_artifact_kind.value,
                )
            )
            for auxiliary in family.auxiliaries:
                identity = (auxiliary.source_url, auxiliary.sha256)
                if identity in auxiliary_identities:
                    continue
                auxiliary_identities.add(identity)
                files.append(
                    ModelInstallFile(
                        family_id=recommendation.family_id,
                        role=auxiliary.role,
                        artifact_kind=auxiliary.artifact_kind,
                        source=ModelInstallSource.TRUSTED_FAMILY_ASSET,
                        model_id=_auxiliary_model_id(auxiliary.role),
                        version_id=1,
                        display_name=auxiliary.filename,
                        file_name=auxiliary.filename,
                        source_url=auxiliary.source_url,
                        sha256=auxiliary.sha256,
                        size_bytes=auxiliary.size_bytes,
                        destination_dir=(
                            root / auxiliary.artifact_kind.value / auxiliary.subfolder
                        ),
                    )
                )
        return ModelInstallPlan(
            model_root=root,
            files=tuple(files),
            available_bytes=self._free_space(root),
        )


class ModelInstallService:
    """Acquire a confirmed plan with exact monotonic aggregate progress."""

    def __init__(
        self,
        *,
        primary_acquisition: ModelAcquisitionService,
        trusted_acquisition: ModelAcquisitionService,
    ) -> None:
        """Store independent CivitAI and family-asset trust boundaries."""

        self._primary_acquisition = primary_acquisition
        self._trusted_acquisition = trusted_acquisition

    def acquire(
        self,
        plan: ModelInstallPlan,
        *,
        cancellation: CancellationProbe | None = None,
        on_progress: ModelInstallProgressCallback | None = None,
    ) -> tuple[AcquisitionResult, ...]:
        """Acquire every required file and stop before later setup commit on failure."""

        if not plan.has_sufficient_space:
            raise OSError("The selected models folder does not have enough free space.")
        aggregate_completed = 0
        results: list[AcquisitionResult] = []
        for index, file in enumerate(plan.files):
            acquisition = (
                self._primary_acquisition
                if file.source is ModelInstallSource.CIVITAI
                else self._trusted_acquisition
            )

            def publish(
                progress: AcquisitionProgress, *, current: ModelInstallFile = file
            ) -> None:
                """Project per-file bytes into a monotonic aggregate measurement."""

                if on_progress is not None:
                    on_progress(
                        ModelInstallProgress(
                            file=current,
                            file_received_bytes=progress.bytes_received,
                            file_expected_bytes=progress.expected_bytes,
                            aggregate_received_bytes=aggregate_completed
                            + progress.bytes_received,
                            aggregate_expected_bytes=plan.total_bytes,
                            completed_files=index,
                            total_files=len(plan.files),
                        )
                    )

            result = acquisition.acquire(
                _as_discovered_model(file),
                destination_dir=file.destination_dir,
                cancellation=cancellation,
                on_progress=publish,
            )
            results.append(result)
            aggregate_completed += file.size_bytes
            if on_progress is not None:
                on_progress(
                    ModelInstallProgress(
                        file=file,
                        file_received_bytes=file.size_bytes,
                        file_expected_bytes=file.size_bytes,
                        aggregate_received_bytes=aggregate_completed,
                        aggregate_expected_bytes=plan.total_bytes,
                        completed_files=index + 1,
                        total_files=len(plan.files),
                    )
                )
        return tuple(results)


def trusted_recipe_url_validator(
    catalog: SupportedModelFamilyCatalog = SUPPORTED_MODEL_FAMILIES,
) -> Callable[[str], None]:
    """Return an exact allowlist validator for checksum-pinned family assets."""

    allowed = frozenset(
        asset.source_url
        for family in catalog.families()
        for asset in family.auxiliaries
    )

    def validate(url: str) -> None:
        """Reject every URL not owned by the shipped family catalog."""

        if url not in allowed:
            raise ValueError("Recipe asset URL is not in the trusted family catalog.")

    return validate


def _as_discovered_model(file: ModelInstallFile) -> DiscoveredModel:
    """Adapt one reviewed install file to the hardened acquisition primitive."""

    return DiscoveredModel(
        artifact_kind=file.artifact_kind,
        model_id=file.model_id,
        version_id=file.version_id,
        model_name=file.display_name,
        version_name=file.display_name,
        creator=None,
        base_model=file.family_id.value,
        file_name=file.file_name,
        size_bytes=file.size_bytes,
        sha256=file.sha256,
        download_url=file.source_url,
        model_page_url="",
        thumbnail_url=None,
        provider_rank=1,
    )


def _free_space(path: Path) -> int:
    """Return free bytes at the nearest existing ancestor."""

    probe = path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def _auxiliary_model_id(role: ModelRecipeRole) -> int:
    """Return a stable positive reservation identity for trusted auxiliaries."""

    return {
        ModelRecipeRole.TEXT_ENCODER: 1,
        ModelRecipeRole.VAE: 2,
        ModelRecipeRole.PRIMARY_MODEL: 3,
    }[role]


__all__ = [
    "DiskSpaceProvider",
    "ModelInstallProgressCallback",
    "ModelInstallRecipePlanner",
    "ModelInstallService",
    "trusted_recipe_url_validator",
]
