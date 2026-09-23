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

"""Record model usage and check only used models for compatible updates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from sugarsubstitute_shared.model_discovery.models import (
    DiscoveredModel,
    ModelArtifactKind,
)
from sugarsubstitute_shared.model_updates.models import (
    ModelUpdatePreferences,
    ModelUpdateProposal,
    ModelUsageRecord,
)

_UPDATE_KINDS = frozenset(
    {
        ModelArtifactKind.CHECKPOINTS,
        ModelArtifactKind.DIFFUSION_MODELS,
        ModelArtifactKind.LORAS,
    }
)


class ModelUsageRepository(Protocol):
    """Persist authoritative model usage outside disposable cache storage."""

    def load(self) -> tuple[ModelUsageRecord, ...]:
        """Return every durable usage record."""

    def save(self, records: tuple[ModelUsageRecord, ...]) -> None:
        """Atomically replace the authoritative usage collection."""


class CompatibleUpdateGateway(Protocol):
    """Find a newer safe version of the exact provider model family."""

    def latest_compatible(
        self,
        *,
        model_id: int,
        current_version_id: int,
        artifact_kind: ModelArtifactKind,
        base_model: str | None,
    ) -> DiscoveredModel | None:
        """Return a strictly newer compatible candidate or none."""

    def compatible_family(
        self,
        *,
        model_id: int,
        current_version_id: int,
        artifact_kind: ModelArtifactKind,
        base_model: str | None,
    ) -> tuple[DiscoveredModel, ...]:
        """Return the verified same-kind chronology oldest to newest."""


class ModelUpdateService:
    """Own usage relevance, explicit consent, and fail-closed update proposals."""

    def __init__(
        self,
        *,
        usage: ModelUsageRepository,
        updates: CompatibleUpdateGateway,
        clock: Callable[[], datetime] | None = None,
        relevance_days: int = 90,
        installed_hashes: Callable[[ModelArtifactKind], frozenset[str]] | None = None,
    ) -> None:
        """Store persistence, provider, clock, and relevance policy."""

        if relevance_days < 1:
            raise ValueError("Model update relevance window must be positive.")
        self._usage = usage
        self._updates = updates
        self._clock = clock or (lambda: datetime.now(tz=UTC))
        self._relevance_days = relevance_days
        self._installed_hashes = installed_hashes or (lambda _kind: frozenset())

    def record_usage(
        self,
        *,
        sha256: str,
        path: Path,
        artifact_kind: ModelArtifactKind,
        model_id: int | None,
        version_id: int | None,
        base_model: str | None,
    ) -> ModelUsageRecord:
        """Atomically count one Generate dispatch against an exact local model."""

        normalized_hash = _sha256(sha256)
        now = _aware_utc(self._clock())
        records = list(self._usage.load())
        matching_index = next(
            (
                index
                for index, record in enumerate(records)
                if record.sha256.casefold() == normalized_hash
            ),
            None,
        )
        previous = records[matching_index] if matching_index is not None else None
        effective_model_id = (
            model_id if model_id is not None else getattr(previous, "model_id", None)
        )
        record = ModelUsageRecord(
            sha256=normalized_hash,
            path=path,
            artifact_kind=artifact_kind,
            model_id=effective_model_id,
            version_id=(
                version_id
                if version_id is not None
                else getattr(previous, "version_id", None)
            ),
            base_model=(
                base_model
                if base_model is not None
                else getattr(previous, "base_model", None)
            ),
            usage_count=(previous.usage_count + 1 if previous is not None else 1),
            last_used_at=now,
            dismissed_version_id=(
                previous.dismissed_version_id if previous is not None else None
            ),
            updates_disabled_for_model=(
                effective_model_id is not None
                and any(
                    item.model_id == effective_model_id
                    and item.updates_disabled_for_model
                    for item in records
                )
            ),
        )
        if matching_index is None:
            records.append(record)
        else:
            records[matching_index] = record
        self._usage.save(tuple(records))
        return record

    def check_updates(
        self,
        preferences: ModelUpdatePreferences,
    ) -> tuple[ModelUpdateProposal, ...]:
        """Return updates only after opt-in and only for recently used known models."""

        if not preferences.enabled:
            return ()
        cutoff = _aware_utc(self._clock()) - timedelta(days=self._relevance_days)
        proposals: list[ModelUpdateProposal] = []
        local_hashes_by_kind: dict[ModelArtifactKind, frozenset[str]] = {}
        records = self._usage.load()
        disabled_model_ids = {
            record.model_id
            for record in records
            if record.updates_disabled_for_model and record.model_id is not None
        }
        for record in sorted(
            records,
            key=lambda item: item.last_used_at,
            reverse=True,
        ):
            if (
                _aware_utc(record.last_used_at) < cutoff
                or record.artifact_kind not in _UPDATE_KINDS
                or record.model_id is None
                or record.model_id in disabled_model_ids
                or record.version_id is None
            ):
                continue
            candidate = self._updates.latest_compatible(
                model_id=record.model_id,
                current_version_id=record.version_id,
                artifact_kind=record.artifact_kind,
                base_model=record.base_model,
            )
            if (
                candidate is not None
                and candidate.sha256.casefold() != record.sha256.casefold()
                and candidate.version_id != record.dismissed_version_id
            ):
                if record.artifact_kind not in local_hashes_by_kind:
                    local_hashes_by_kind[record.artifact_kind] = (
                        self.installed_hashes_for_kind(record.artifact_kind)
                    )
                local_hashes = local_hashes_by_kind[record.artifact_kind]
                if candidate.sha256.casefold() in local_hashes:
                    continue
                proposals.append(ModelUpdateProposal(record, candidate))
        return tuple(proposals)

    def installed_hashes_for_kind(self, kind: ModelArtifactKind) -> frozenset[str]:
        """Return known local hashes from the authoritative model catalog."""

        return frozenset(value.casefold() for value in self._installed_hashes(kind))

    def dismiss_update(self, *, sha256: str, version_id: int) -> bool:
        """Hide one candidate for this model until a newer version appears."""

        if version_id <= 0:
            raise ValueError("Dismissed model version must be positive.")
        normalized_hash = _sha256(sha256)
        records = list(self._usage.load())
        for index, record in enumerate(records):
            if record.sha256.casefold() == normalized_hash:
                records[index] = replace(record, dismissed_version_id=version_id)
                self._usage.save(tuple(records))
                return True
        return False

    def disable_model_updates(self, model_id: int) -> bool:
        """Stop checking every local version from one provider model page."""

        if model_id <= 0:
            raise ValueError("Provider model page identifier must be positive.")
        records = self._usage.load()
        if not any(record.model_id == model_id for record in records):
            return False
        self._usage.save(
            tuple(
                replace(record, updates_disabled_for_model=True)
                if record.model_id == model_id
                else record
                for record in records
            )
        )
        return True

    def version_family(
        self, proposal: ModelUpdateProposal
    ) -> tuple[DiscoveredModel, ...]:
        """Load one visible proposal's exact type/base family for inspection."""

        current = proposal.current
        if (
            current.artifact_kind not in _UPDATE_KINDS
            or current.model_id is None
            or current.version_id is None
            or not any(
                record.sha256 == current.sha256
                and record.artifact_kind is current.artifact_kind
                and record.model_id == current.model_id
                and record.version_id == current.version_id
                for record in self._usage.load()
            )
        ):
            return ()
        return self._updates.compatible_family(
            model_id=current.model_id,
            current_version_id=current.version_id,
            artifact_kind=current.artifact_kind,
            base_model=current.base_model,
        )


def _sha256(value: str) -> str:
    """Return a normalized exact SHA256 identity."""

    normalized = value.casefold()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError("Model usage SHA256 is invalid.")
    return normalized


def _aware_utc(value: datetime) -> datetime:
    """Normalize one timestamp to aware UTC for deterministic comparison."""

    if value.tzinfo is None:
        raise ValueError("Model usage timestamps must be timezone-aware.")
    return value.astimezone(UTC)


__all__ = ["CompatibleUpdateGateway", "ModelUpdateService", "ModelUsageRepository"]
