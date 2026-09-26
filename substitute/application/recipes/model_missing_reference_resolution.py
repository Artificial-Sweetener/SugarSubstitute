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

"""Resolve missing recipe model metadata without serial network stalls."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.model_metadata.ports import CivitaiMetadataGateway
from substitute.domain.model_metadata import (
    CivitaiDownloadAccess,
    CivitaiLookupResult,
    CivitaiLookupStatus,
    CivitaiThumbnailPolicy,
)
from substitute.infrastructure.execution.parallel_map import BoundedParallelMapper

from .model_download_candidate import (
    RecipeModelDownloadCandidate,
    RecipeModelRecoveryGateway,
    candidate_from_civitai_version,
    candidate_from_recovery_gateways,
    civitai_download_access,
)
from .model_resolution_models import (
    RecipeModelCivitaiState,
    RecipeModelUnresolvedReference,
)

_MAX_CIVITAI_LOOKUP_PARALLELISM = 8


@dataclass(frozen=True, slots=True)
class MissingRecipeModelReference:
    """Describe one unresolved hash before external recovery enrichment."""

    alias: str
    node_name: str
    input_key: str
    kind: str
    value: str
    sha256: str


@dataclass(frozen=True, slots=True)
class _CivitaiEvidence:
    """Retain one CivitAI lookup and its optional download-access evidence."""

    lookup: CivitaiLookupResult
    download_access: CivitaiDownloadAccess = CivitaiDownloadAccess.UNKNOWN


class RecipeModelMissingReferenceResolver:
    """Enrich missing references with deduplicated concurrent provider evidence."""

    def __init__(
        self,
        *,
        civitai: CivitaiMetadataGateway | None,
        civitai_lookup_enabled: bool,
        thumbnail_policy: CivitaiThumbnailPolicy,
        recovery_gateways: tuple[RecipeModelRecoveryGateway, ...],
    ) -> None:
        """Store provider policy for one recipe-resolution request."""

        self._civitai = civitai
        self._civitai_lookup_enabled = civitai_lookup_enabled
        self._thumbnail_policy = thumbnail_policy
        self._recovery_gateways = recovery_gateways

    def resolve(
        self,
        references: tuple[MissingRecipeModelReference, ...],
    ) -> tuple[RecipeModelUnresolvedReference, ...]:
        """Return ordered unresolved references with bounded provider latency."""

        recovery_candidates = self._recovery_candidates(references)
        pending_hashes = tuple(
            dict.fromkeys(
                reference.sha256.upper()
                for reference in references
                if recovery_candidates[(reference.kind, reference.sha256.upper())]
                is None
            )
        )
        civitai_evidence = self._civitai_evidence(pending_hashes)
        return tuple(
            self._resolved_reference(
                reference,
                recovery_candidate=recovery_candidates[
                    (reference.kind, reference.sha256.upper())
                ],
                civitai_evidence=civitai_evidence.get(reference.sha256.upper()),
            )
            for reference in references
        )

    def _recovery_candidates(
        self,
        references: tuple[MissingRecipeModelReference, ...],
    ) -> dict[tuple[str, str], RecipeModelDownloadCandidate | None]:
        """Resolve each provider-specific model identity once."""

        identities = dict.fromkeys(
            (reference.kind, reference.sha256.upper()) for reference in references
        )
        return {
            identity: candidate_from_recovery_gateways(
                self._recovery_gateways,
                kind=identity[0],
                sha256=identity[1],
            )
            for identity in identities
        }

    def _civitai_evidence(
        self,
        hashes: tuple[str, ...],
    ) -> dict[str, _CivitaiEvidence]:
        """Look up unique hashes concurrently within one provider timeout window."""

        civitai = self._civitai
        if not hashes or not self._civitai_lookup_enabled or civitai is None:
            return {}
        parallelism = min(len(hashes), _MAX_CIVITAI_LOOKUP_PARALLELISM)
        with BoundedParallelMapper(parallelism=parallelism) as parallel_mapper:
            evidence = parallel_mapper.map(self._lookup_civitai_evidence, hashes)
        return dict(zip(hashes, evidence, strict=True))

    def _lookup_civitai_evidence(self, sha256: str) -> _CivitaiEvidence:
        """Fetch one hash and access policy within the bounded lookup batch."""

        civitai = self._civitai
        assert civitai is not None
        lookup = civitai.lookup_model_version_by_hash(sha256)
        if lookup.status is not CivitaiLookupStatus.FOUND or lookup.version is None:
            return _CivitaiEvidence(lookup)
        return _CivitaiEvidence(
            lookup,
            civitai_download_access(civitai, lookup.version.model_version_id),
        )

    def _resolved_reference(
        self,
        reference: MissingRecipeModelReference,
        *,
        recovery_candidate: RecipeModelDownloadCandidate | None,
        civitai_evidence: _CivitaiEvidence | None,
    ) -> RecipeModelUnresolvedReference:
        """Project provider evidence into the public unresolved-reference model."""

        sha256 = reference.sha256.upper()
        if recovery_candidate is not None:
            return _reference(
                reference,
                sha256=sha256,
                state=RecipeModelCivitaiState.FOUND,
                candidate=recovery_candidate,
            )
        if not self._civitai_lookup_enabled:
            return _reference(
                reference,
                sha256=sha256,
                state=RecipeModelCivitaiState.DISABLED,
            )
        if self._civitai is None or civitai_evidence is None:
            return _reference(
                reference,
                sha256=sha256,
                state=RecipeModelCivitaiState.UNAVAILABLE,
                status=CivitaiLookupStatus.UNAVAILABLE,
            )
        lookup = civitai_evidence.lookup
        if lookup.status is not CivitaiLookupStatus.FOUND or lookup.version is None:
            return _reference(
                reference,
                sha256=sha256,
                state=(
                    RecipeModelCivitaiState.NOT_FOUND
                    if lookup.status is CivitaiLookupStatus.NOT_FOUND
                    else RecipeModelCivitaiState.UNAVAILABLE
                ),
                status=lookup.status,
                error=lookup.error,
            )
        candidate = candidate_from_civitai_version(
            kind=reference.kind,
            sha256=sha256,
            version=lookup.version,
            thumbnail_policy=self._thumbnail_policy,
            download_access=civitai_evidence.download_access,
        )
        return _reference(
            reference,
            sha256=sha256,
            state=(
                RecipeModelCivitaiState.FOUND
                if candidate is not None
                else RecipeModelCivitaiState.NO_SAFE_FILE
            ),
            status=lookup.status,
            candidate=candidate,
        )


def _reference(
    source: MissingRecipeModelReference,
    *,
    sha256: str,
    state: RecipeModelCivitaiState,
    status: CivitaiLookupStatus | None = None,
    error: str | None = None,
    candidate: RecipeModelDownloadCandidate | None = None,
) -> RecipeModelUnresolvedReference:
    """Build one public reference while preserving workflow field identity."""

    return RecipeModelUnresolvedReference(
        alias=source.alias,
        node_name=source.node_name,
        input_key=source.input_key,
        kind=source.kind,
        value=source.value,
        sha256=sha256,
        civitai_state=state,
        civitai_status=status,
        civitai_error=error,
        candidate=candidate,
    )


__all__ = [
    "MissingRecipeModelReference",
    "RecipeModelMissingReferenceResolver",
]
