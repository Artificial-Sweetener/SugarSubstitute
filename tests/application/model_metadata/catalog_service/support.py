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

"""Shared deterministic fixtures for model-catalog service contracts."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.model_metadata import (
    BackendFingerprint,
    BackendFingerprintJob,
    BackendLocalPreview,
    BackendModelCatalogEntry,
    BackendModelFile,
    BackendModelSource,
    BackendSidecar,
    CivitaiModelVersion,
    FingerprintStatus,
    JobStatus,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailSelectionStatus,
    ThumbnailStoreResult,
    ThumbnailVariant,
)


class _FakeBackend:
    """Return deterministic backend model catalog entries."""

    def __init__(self, entries: tuple[BackendModelCatalogEntry, ...]) -> None:
        """Store fake entries for requested kind filtering."""

        self.entries = entries
        self.list_model_calls: list[tuple[tuple[str, ...], bool]] = []

    def get_capabilities(self) -> None:
        """Return no capabilities because catalog tests do not use this method."""

        return None

    def refresh_fingerprints(
        self,
        entries: tuple[BackendModelCatalogEntry, ...],
    ) -> BackendFingerprintJob:
        """Return an empty fingerprint job because catalog tests do not use this method."""

        _ = entries
        return BackendFingerprintJob(
            job_id="unused",
            status=JobStatus.COMPLETE,
            entries=(),
        )

    def get_fingerprint_job(self, job_id: str) -> BackendFingerprintJob | None:
        """Return no fingerprint job because catalog tests do not use this method."""

        _ = job_id
        return None

    def list_models(
        self,
        kinds: tuple[str, ...],
        *,
        refresh: bool = False,
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Return fake model entries for the requested model kinds."""

        self.list_model_calls.append((kinds, refresh))
        return tuple(entry for entry in self.entries if entry.kind in kinds)


class _FakeCatalog:
    """Return deterministic cached metadata records."""

    def __init__(self, records: tuple[ModelMetadataCacheRecord, ...]) -> None:
        """Store fake records for requested kind filtering."""

        self.records = records

    def list_records(
        self,
        *,
        kind: str | None = None,
    ) -> tuple[ModelMetadataCacheRecord, ...]:
        """Return fake metadata records filtered by kind."""

        if kind is None:
            return self.records
        return tuple(record for record in self.records if record.local.kind == kind)


def _entry(
    kind: str,
    value: str,
    sha256: str | None,
    *,
    display_name: str | None = None,
    sidecar_base_model: str | None = None,
) -> BackendModelCatalogEntry:
    """Return one backend model catalog entry."""

    suffix = Path(value.replace("\\", "/")).suffix or ".safetensors"
    return BackendModelCatalogEntry(
        schema_version=1,
        target_id=f"target-{kind}-{sha256 or value}",
        kind=kind,
        value=value,
        display_name=display_name if display_name is not None else Path(value).stem,
        source=BackendModelSource(root_id="root", relative_path=value),
        file=BackendModelFile(
            extension=suffix,
            size_bytes=123,
            modified_at="2026-04-14T01:00:00Z",
            created_at=None,
        ),
        fingerprint=BackendFingerprint(
            status=FingerprintStatus.READY if sha256 else FingerprintStatus.MISSING,
            sha256=sha256,
            source="backend" if sha256 else None,
            computed_at="2026-04-14T01:00:00Z" if sha256 else None,
            error=None,
        ),
        sidecar=BackendSidecar(
            found=sidecar_base_model is not None,
            model_id=None,
            model_version_id=None,
            sha256=None,
            activation_text=None,
            description=None,
            base_model=sidecar_base_model,
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


def _record(
    *,
    kind: str,
    value: str,
    sha256: str,
    model_name: str,
    version_name: str = "Version",
    base_model: str | None = "Base",
    variants: tuple[ThumbnailVariant, ...] | None = None,
) -> ModelMetadataCacheRecord:
    """Return one cached CivitAI metadata record."""

    resolved_variants = variants
    if resolved_variants is None:
        resolved_variants = (
            ThumbnailVariant(
                size=128,
                storage_key=f"{sha256}:128",
                width=85,
                height=128,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=65536,
            ),
        )
    return ModelMetadataCacheRecord(
        schema_version=1,
        local=LocalModelEvidence(
            target_id=f"target-{sha256}",
            root_id="root",
            relative_path=value,
            kind=kind,
            value=value,
            display_name=Path(value.replace("\\", "/")).stem,
            size_bytes=123,
            modified_at="2026-04-14T01:00:00Z",
            sha256=sha256,
        ),
        provider=CivitaiModelVersion(
            model_id=1,
            model_version_id=2,
            model_name=model_name,
            model_type="Checkpoint",
            version_name=version_name,
            base_model=base_model,
            trained_words=("trigger",),
            description=None,
            version_description=None,
            tags=("tag",),
            creator_username=None,
            creator_image=None,
            nsfw=False,
            nsfw_level="None",
            availability=None,
            files=(),
            images=(),
            stats={},
            model_page_url="https://civitai.com/models/1?modelVersionId=2",
            source_url="https://civitai.example/model",
            fetched_at="2026-04-14T12:00:00Z",
            raw_provider_payload={},
        ),
        provider_status="found",
        thumbnail=ThumbnailStoreResult(
            source="civitai",
            selection_policy="first-sfw-version-image",
            source_image_url="https://image.example/image.jpg",
            source_image_id=1,
            nsfw=False,
            nsfw_level="None",
            source_width=512,
            source_height=768,
            variants=resolved_variants,
            downloaded_at="2026-04-14T12:00:00Z",
        ),
        thumbnail_status=ThumbnailSelectionStatus.SELECTED,
        updated_at="2026-04-14T12:00:00Z",
    )
