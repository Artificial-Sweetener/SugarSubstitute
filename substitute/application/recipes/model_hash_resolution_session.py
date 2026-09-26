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

"""Bound and reuse authoritative model-hash lookups for one recipe load."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.model_metadata.ports import (
    BackendModelHashLookupGateway,
    BackendModelMetadataGateway,
)
from substitute.domain.model_metadata import (
    BackendHashLookupMatch,
    BackendHashLookupStatus,
    JobStatus,
)

from .model_resolution_index import LocalRecipeModel, RecipeModelResolutionIndex


@dataclass(frozen=True, slots=True)
class _BackendHashResolution:
    """Distinguish an authoritative miss from transport unavailability."""

    available: bool
    model: LocalRecipeModel | None


class RecipeModelHashResolutionSession:
    """Resolve model hashes within one shared polling budget and result cache."""

    def __init__(
        self,
        *,
        index: RecipeModelResolutionIndex,
        backend: BackendModelHashLookupGateway | None,
        fingerprint_jobs: BackendModelMetadataGateway | None,
        sleep: Callable[[float], None],
        monotonic: Callable[[], float],
        poll_interval_seconds: float,
        poll_timeout_seconds: float,
    ) -> None:
        """Create one request-scoped hash lookup policy."""

        self._index = index
        self._backend = backend
        self._fingerprint_jobs = fingerprint_jobs
        self._sleep = sleep
        self._monotonic = monotonic
        self._poll_interval_seconds = poll_interval_seconds
        self._deadline = monotonic() + poll_timeout_seconds
        self._backend_available = backend is not None
        self._results: dict[tuple[str, str], LocalRecipeModel | None] = {}

    def resolve(self, *, kind: str, sha256: str) -> LocalRecipeModel | None:
        """Return authoritative or cached evidence for one normalized identity."""

        key = (kind, sha256.upper())
        if key in self._results:
            return self._results[key]
        if not self._backend_available or self._monotonic() >= self._deadline:
            model = self._index.find_hash(kind=kind, sha256=sha256)
            self._results[key] = model
            return model
        resolution = self._resolve_from_backend(kind=kind, sha256=sha256)
        if resolution.available:
            model = resolution.model
        else:
            self._backend_available = False
            model = self._index.find_hash(kind=kind, sha256=sha256)
        self._results[key] = model
        return model

    def _resolve_from_backend(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> _BackendHashResolution:
        """Ask Substitute BackEnd for current local hash evidence."""

        backend = self._backend
        if backend is None:
            return _BackendHashResolution(available=False, model=None)
        while self._monotonic() < self._deadline:
            result = backend.lookup_model_by_hash(kind=kind, sha256=sha256)
            if result is None:
                return _BackendHashResolution(available=False, model=None)
            if result.status is BackendHashLookupStatus.COMPLETE:
                return _BackendHashResolution(
                    available=True,
                    model=(
                        _model_from_backend_match(result.matches[0], sha256)
                        if result.matches
                        else None
                    ),
                )
            if result.status not in {
                BackendHashLookupStatus.HASHING_REQUIRED,
                BackendHashLookupStatus.HASHING_RUNNING,
            }:
                return _BackendHashResolution(available=True, model=None)
            if result.job_id is None or self._fingerprint_jobs is None:
                return _BackendHashResolution(available=True, model=None)
            if not self._wait_for_hash_job(result.job_id):
                return _BackendHashResolution(available=False, model=None)
        return _BackendHashResolution(available=True, model=None)

    def _wait_for_hash_job(self, job_id: str) -> bool:
        """Wait for a hash job and report whether its BackEnd stayed available."""

        fingerprint_jobs = self._fingerprint_jobs
        if fingerprint_jobs is None:
            return True
        while self._monotonic() < self._deadline:
            job = fingerprint_jobs.get_fingerprint_job(job_id)
            if job is None:
                return False
            if job.status not in {JobStatus.QUEUED, JobStatus.RUNNING}:
                return True
            self._sleep(self._poll_interval_seconds)
        return True


def _model_from_backend_match(
    match: BackendHashLookupMatch,
    sha256: str,
) -> LocalRecipeModel:
    """Convert one typed BackEnd match without leaking its transport model."""

    return LocalRecipeModel(
        kind=match.kind,
        backend_value=match.value,
        display_name=match.display_name,
        relative_path=match.source.relative_path,
        sha256=sha256.upper(),
    )


__all__ = ["RecipeModelHashResolutionSession"]
