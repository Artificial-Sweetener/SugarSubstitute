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

"""Verify request-scoped model hash polling, caching, and fallback policy."""

from __future__ import annotations

from typing import cast

import pytest

from substitute.application.model_metadata.ports import (
    BackendModelHashLookupGateway,
    BackendModelMetadataGateway,
)
from substitute.application.recipes.model_hash_resolution_session import (
    RecipeModelHashResolutionSession,
)
from substitute.application.recipes.model_resolution_index import (
    RecipeModelResolutionIndex,
)
from substitute.application.recipes import (
    RecipeModelLoadResolver,
    RecipeModelResolutionRequired,
)
from substitute.domain.model_metadata import (
    BackendFingerprintJob,
    BackendHashLookupMatch,
    BackendHashLookupResult,
    BackendHashLookupStatus,
    BackendModelFile,
    BackendModelSource,
    JobStatus,
)
from substitute.domain.recipes.sugar_script_parser import parse_sugar_script_document


def test_session_shares_one_fingerprint_budget_across_workflow() -> None:
    """Do not restart the full fingerprint timeout for every model field."""

    clock = _AdvancingClock()
    backend = _RunningFingerprintBackend()
    session = RecipeModelHashResolutionSession(
        index=RecipeModelResolutionIndex(()),
        backend=cast(BackendModelHashLookupGateway, backend),
        fingerprint_jobs=cast(BackendModelMetadataGateway, backend),
        sleep=clock.advance,
        monotonic=clock.now,
        poll_interval_seconds=0.5,
        poll_timeout_seconds=1.0,
    )

    assert session.resolve(kind="checkpoints", sha256="1" * 64) is None
    assert session.resolve(kind="checkpoints", sha256="2" * 64) is None
    assert backend.lookups == [("checkpoints", "1" * 64)]
    assert backend.polled_job_ids == ["job-1", "job-1"]


def test_session_reuses_one_authoritative_result_for_duplicate_fields() -> None:
    """Resolve a repeated model identity once for the whole workflow."""

    sha256 = "3" * 64
    backend = _MatchingBackend("Installed/shared.safetensors")
    session = RecipeModelHashResolutionSession(
        index=RecipeModelResolutionIndex(()),
        backend=cast(BackendModelHashLookupGateway, backend),
        fingerprint_jobs=None,
        sleep=lambda _seconds: None,
        monotonic=lambda: 0.0,
        poll_interval_seconds=0.5,
        poll_timeout_seconds=120.0,
    )

    first = session.resolve(kind="checkpoints", sha256=sha256)
    second = session.resolve(kind="checkpoints", sha256=sha256)

    assert first is second
    assert first is not None
    assert first.backend_value == "Installed/shared.safetensors"
    assert backend.lookups == [("checkpoints", sha256)]


def test_resolver_default_hash_polling_budget_is_interactive() -> None:
    """Stop waiting for background fingerprinting after five shared seconds."""

    sha256 = "4" * 64
    clock = _AdvancingClock()
    backend = _RunningFingerprintBackend()
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(()),
        backend=cast(BackendModelHashLookupGateway, backend),
        fingerprint_jobs=cast(BackendModelMetadataGateway, backend),
        civitai_missing_model_lookup_enabled=lambda: False,
        sleep=clock.advance,
        monotonic=clock.now,
    )
    script = parse_sugar_script_document(
        "\n".join(
            (
                "use X as A",
                'set A.checkpoint.ckpt_name = "missing.safetensors"',
                f"# sha256 {sha256}",
                "",
            )
        )
    )

    with pytest.raises(RecipeModelResolutionRequired):
        resolver.resolve(script)

    assert clock.now() == 5.0
    assert backend.lookups == [("checkpoints", sha256)]


class _AdvancingClock:
    """Provide deterministic monotonic time advanced by resolver sleeps."""

    def __init__(self) -> None:
        """Start at monotonic zero."""

        self._value = 0.0

    def now(self) -> float:
        """Return deterministic monotonic time."""

        return self._value

    def advance(self, seconds: float) -> None:
        """Advance deterministic monotonic time by one polling interval."""

        self._value += seconds


class _RunningFingerprintBackend:
    """Keep one fingerprint job running until the operation budget expires."""

    def __init__(self) -> None:
        """Create empty request records."""

        self.lookups: list[tuple[str, str]] = []
        self.polled_job_ids: list[str] = []

    def lookup_model_by_hash(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> BackendHashLookupResult:
        """Return a running fingerprint job for every requested identity."""

        self.lookups.append((kind, sha256))
        return BackendHashLookupResult(
            status=BackendHashLookupStatus.HASHING_RUNNING,
            kind=kind,
            sha256=sha256,
            matches=(),
            job_id=f"job-{len(self.lookups)}",
        )

    def get_fingerprint_job(self, job_id: str) -> BackendFingerprintJob:
        """Keep the requested job running while recording each poll."""

        self.polled_job_ids.append(job_id)
        return BackendFingerprintJob(
            job_id=job_id,
            status=JobStatus.RUNNING,
            entries=(),
        )


class _MatchingBackend:
    """Return one installed model for an exact hash."""

    def __init__(self, value: str) -> None:
        """Store the returned backend value."""

        self._value = value
        self.lookups: list[tuple[str, str]] = []

    def lookup_model_by_hash(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> BackendHashLookupResult:
        """Return one complete authoritative match."""

        self.lookups.append((kind, sha256))
        return BackendHashLookupResult(
            status=BackendHashLookupStatus.COMPLETE,
            kind=kind,
            sha256=sha256,
            matches=(
                BackendHashLookupMatch(
                    kind=kind,
                    value=self._value,
                    display_name="shared",
                    source=BackendModelSource(
                        root_id="checkpoints:0",
                        relative_path=self._value,
                    ),
                    file=BackendModelFile(
                        extension=".safetensors",
                        size_bytes=1,
                        modified_at="2026-09-25T00:00:00Z",
                        created_at=None,
                    ),
                ),
            ),
            job_id=None,
        )
