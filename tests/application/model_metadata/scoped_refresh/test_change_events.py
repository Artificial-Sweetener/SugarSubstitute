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

"""Tests for scoped metadata refresh from catalog change events."""

from __future__ import annotations

from typing import Any, cast

from substitute.application.model_metadata import (
    ModelMetadataRefreshSummary,
    ScopedMetadataRefreshService,
)
from substitute.domain.model_metadata import (
    BackendFingerprint,
    BackendLocalPreview,
    BackendModelCatalogChangedEntry,
    BackendModelCatalogChangedFile,
    BackendModelCatalogChangedSource,
    BackendModelCatalogEntry,
    BackendModelFile,
    BackendModelSource,
    BackendSidecar,
    FingerprintStatus,
)
from tests.support.execution import ImmediateTaskSubmitter


def test_scoped_metadata_refresh_deduplicates_and_matches_backend_entries() -> None:
    """Enrich each changed backend entry at most once."""

    backend_entry = _backend_entry("style.safetensors")
    backend = _Backend((backend_entry,))
    refresh_service = _RefreshService()
    service = ScopedMetadataRefreshService(
        backend=cast(Any, backend),
        refresh_service=cast(Any, refresh_service),
        update_sink=cast(Any, _UpdateSink()),
        submitter=ImmediateTaskSubmitter(),
        batch_size=4,
    )
    changed = _changed_entry("style.safetensors")

    service.queue_entries((changed, changed))

    assert backend.calls == [("loras",)]
    assert refresh_service.calls == [(backend_entry,)]


class _Backend:
    """Return configured backend catalog entries."""

    def __init__(self, entries: tuple[BackendModelCatalogEntry, ...]) -> None:
        """Store fake catalog entries."""

        self.entries = entries
        self.calls: list[tuple[str, ...]] = []

    def list_models(
        self, kinds: tuple[str, ...], *, refresh: bool = False
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Return entries matching requested kinds."""

        del refresh
        self.calls.append(kinds)
        return tuple(entry for entry in self.entries if entry.kind in kinds)


class _RefreshService:
    """Collect scoped refresh requests."""

    def __init__(self) -> None:
        """Initialize empty refresh call list."""

        self.calls: list[tuple[BackendModelCatalogEntry, ...]] = []

    def refresh_entries(
        self,
        models: tuple[BackendModelCatalogEntry, ...],
        progress: object,
        *,
        cancellation_token: object | None = None,
    ) -> ModelMetadataRefreshSummary:
        """Record models selected for refresh."""

        del progress, cancellation_token
        self.calls.append(models)
        return ModelMetadataRefreshSummary(discovered=len(models), enriched=len(models))


class _UpdateSink:
    """Accept metadata updates without side effects."""

    def emit_model_updated(self, event: object) -> None:
        """Ignore one metadata update."""

        del event


def _changed_entry(value: str) -> BackendModelCatalogChangedEntry:
    """Build one changed-entry DTO."""

    return BackendModelCatalogChangedEntry(
        kind="loras",
        value=value,
        source=BackendModelCatalogChangedSource(root_id="loras:0", relative_path=value),
        file=BackendModelCatalogChangedFile(
            size_bytes=123, modified_at="2026-05-26T12:00:00Z"
        ),
    )


def _backend_entry(value: str) -> BackendModelCatalogEntry:
    """Build one backend catalog entry for scoped refresh tests."""

    return BackendModelCatalogEntry(
        schema_version=1,
        target_id=f"target:loras:{value}",
        kind="loras",
        value=value,
        display_name="style",
        source=BackendModelSource(root_id="loras:0", relative_path=value),
        file=BackendModelFile(
            extension=".safetensors",
            size_bytes=123,
            modified_at="2026-05-26T12:00:00Z",
            created_at=None,
        ),
        fingerprint=BackendFingerprint(
            status=FingerprintStatus.MISSING,
            sha256=None,
            source=None,
            computed_at=None,
            error=None,
        ),
        sidecar=BackendSidecar(
            found=False,
            model_id=None,
            model_version_id=None,
            sha256=None,
            activation_text=None,
            description=None,
            base_model=None,
            modified_at=None,
        ),
        local_preview=BackendLocalPreview(
            available=False,
            preview_id=None,
            url=None,
            source=None,
            modified_at=None,
            width=None,
            height=None,
        ),
    )
