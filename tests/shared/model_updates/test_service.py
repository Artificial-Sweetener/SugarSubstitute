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

"""Verify opt-in, usage-aware compatible model update planning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sugarsubstitute_shared.model_discovery.models import (
    DiscoveredModel,
    ModelArtifactKind,
)
from sugarsubstitute_shared.model_updates import (
    ModelUpdatePreferences,
    ModelUpdateService,
    ModelUsageRecord,
)


class _Usage:
    """Keep deterministic authoritative usage records in memory."""

    def __init__(self, records: tuple[ModelUsageRecord, ...] = ()) -> None:
        """Store initial records."""

        self.records = records

    def load(self) -> tuple[ModelUsageRecord, ...]:
        """Return current records."""

        return self.records

    def save(self, records: tuple[ModelUsageRecord, ...]) -> None:
        """Replace current records."""

        self.records = records


class _Updates:
    """Return one injected candidate while recording provider calls."""

    def __init__(self, candidate: DiscoveredModel | None) -> None:
        """Store the candidate and initialize call count."""

        self.candidate = candidate
        self.calls = 0

    def latest_compatible(self, **_kwargs: object) -> DiscoveredModel | None:
        """Record and return the candidate."""

        self.calls += 1
        return self.candidate


def _candidate() -> DiscoveredModel:
    """Return a safe side-by-side update candidate."""

    return DiscoveredModel(
        artifact_kind=ModelArtifactKind.CHECKPOINTS,
        model_id=1,
        version_id=3,
        model_name="Model",
        version_name="v3",
        creator="Creator",
        base_model="SDXL",
        file_name="model-v3.safetensors",
        size_bytes=10,
        sha256="b" * 64,
        download_url="https://civitai.com/api/download/models/3",
        model_page_url="https://civitai.com/models/1?modelVersionId=3",
        thumbnail_url=None,
        provider_rank=1,
    )


def test_update_checks_are_disabled_without_explicit_opt_in() -> None:
    """Default preferences must perform no provider request."""

    updates = _Updates(_candidate())
    service = ModelUpdateService(usage=_Usage(), updates=updates)

    assert service.check_updates(ModelUpdatePreferences()) == ()
    assert updates.calls == 0


def test_recent_used_known_model_receives_compatible_update_proposal() -> None:
    """A recent Generate use should make a known provider model relevant."""

    now = datetime(2026, 8, 31, tzinfo=UTC)
    usage = _Usage(
        (
            ModelUsageRecord(
                sha256="a" * 64,
                path=Path("models/current.safetensors"),
                artifact_kind=ModelArtifactKind.CHECKPOINTS,
                model_id=1,
                version_id=2,
                base_model="SDXL",
                usage_count=4,
                last_used_at=now - timedelta(days=1),
            ),
        )
    )
    updates = _Updates(_candidate())

    proposals = ModelUpdateService(
        usage=usage,
        updates=updates,
        clock=lambda: now,
    ).check_updates(ModelUpdatePreferences(enabled=True))

    assert len(proposals) == 1
    assert proposals[0].current.path.name == "current.safetensors"
    assert proposals[0].candidate.version_id == 3


def test_stale_unknown_and_same_hash_models_do_not_alert() -> None:
    """Update alerts should exclude irrelevant, unidentified, and already-owned files."""

    now = datetime(2026, 8, 31, tzinfo=UTC)
    usage = _Usage(
        (
            ModelUsageRecord(
                sha256="b" * 64,
                path=Path("models/current.safetensors"),
                artifact_kind=ModelArtifactKind.CHECKPOINTS,
                model_id=1,
                version_id=2,
                base_model="SDXL",
                usage_count=1,
                last_used_at=now - timedelta(days=100),
            ),
            ModelUsageRecord(
                sha256="c" * 64,
                path=Path("models/unknown.safetensors"),
                artifact_kind=ModelArtifactKind.CHECKPOINTS,
                model_id=None,
                version_id=None,
                base_model=None,
                usage_count=1,
                last_used_at=now,
            ),
        )
    )
    updates = _Updates(_candidate())

    assert (
        ModelUpdateService(
            usage=usage,
            updates=updates,
            clock=lambda: now,
        ).check_updates(ModelUpdatePreferences(enabled=True))
        == ()
    )
    assert updates.calls == 0


def test_record_usage_counts_generate_dispatch_and_preserves_known_identity() -> None:
    """Repeated Generate dispatches should update count/time without losing metadata."""

    first = datetime(2026, 8, 30, tzinfo=UTC)
    second = datetime(2026, 8, 31, tzinfo=UTC)
    ticks = iter((first, second))
    usage = _Usage()
    service = ModelUpdateService(
        usage=usage,
        updates=_Updates(None),
        clock=lambda: next(ticks),
    )

    service.record_usage(
        sha256="a" * 64,
        path=Path("models/model.safetensors"),
        artifact_kind=ModelArtifactKind.CHECKPOINTS,
        model_id=1,
        version_id=2,
        base_model="SDXL",
    )
    updated = service.record_usage(
        sha256="a" * 64,
        path=Path("models/model.safetensors"),
        artifact_kind=ModelArtifactKind.CHECKPOINTS,
        model_id=None,
        version_id=None,
        base_model=None,
    )

    assert updated.usage_count == 2
    assert updated.model_id == 1
    assert updated.version_id == 2
    assert updated.last_used_at == second
