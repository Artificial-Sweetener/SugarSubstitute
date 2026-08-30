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

"""Prompt LoRA catalog test support."""

from __future__ import annotations


from pathlib import Path

from substitute.application.model_metadata import ModelCatalogService
from substitute.application.prompt_editor.lora.catalog import PromptLoraCatalogService
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

    def __init__(
        self,
        entries: tuple[BackendModelCatalogEntry, ...],
        *,
        fail_refresh: bool = False,
    ) -> None:
        """Store fake entries for assertions."""

        self.entries = entries
        self.fail_refresh = fail_refresh
        self.list_model_calls = 0
        self.list_model_refreshes: list[bool] = []

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
        """Return fake model entries for the requested LoRA kind."""

        assert kinds == ("loras",)
        self.list_model_calls += 1
        self.list_model_refreshes.append(refresh)
        if refresh and self.fail_refresh:
            raise RuntimeError("Backend model catalog refresh failed.")
        return self.entries


class _FakeCatalog:
    """Return deterministic cached metadata records."""

    def __init__(self, records: tuple[ModelMetadataCacheRecord, ...]) -> None:
        """Store fake metadata records for assertions."""

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


def _entry(value: str, sha256: str) -> BackendModelCatalogEntry:
    """Return one backend LoRA catalog entry."""

    return BackendModelCatalogEntry(
        schema_version=1,
        target_id=f"target-{sha256}",
        kind="loras",
        value=value,
        display_name=Path(value.replace("\\", "/")).stem,
        source=BackendModelSource(root_id="root", relative_path=value),
        file=BackendModelFile(
            extension=".safetensors",
            size_bytes=123,
            modified_at="2026-04-14T01:00:00Z",
            created_at=None,
        ),
        fingerprint=BackendFingerprint(
            status=FingerprintStatus.READY,
            sha256=sha256,
            source="backend",
            computed_at="2026-04-14T01:00:00Z",
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


def _service(
    *,
    backend: _FakeBackend,
    catalog: _FakeCatalog,
) -> PromptLoraCatalogService:
    """Return a LoRA catalog service using the shared generic model catalog."""

    return PromptLoraCatalogService(
        model_catalog=ModelCatalogService(
            backend=backend,
            metadata_catalog=catalog,
        )
    )


def _record(
    *,
    value: str,
    sha256: str,
    model_name: str,
    version_name: str = "Version",
    model_id: int = 1,
    model_version_id: int = 2,
    storage_key: str | None = None,
) -> ModelMetadataCacheRecord:
    """Return one cached CivitAI metadata record."""

    resolved_storage_key = storage_key if storage_key is not None else f"{sha256}:128"
    return ModelMetadataCacheRecord(
        schema_version=1,
        local=LocalModelEvidence(
            target_id=f"target-{sha256}",
            root_id="root",
            relative_path=value,
            kind="loras",
            value=value,
            display_name=Path(value.replace("\\", "/")).stem,
            size_bytes=123,
            modified_at="2026-04-14T01:00:00Z",
            sha256=sha256,
        ),
        provider=CivitaiModelVersion(
            model_id=model_id,
            model_version_id=model_version_id,
            model_name=model_name,
            model_type="LORA",
            version_name=version_name,
            base_model="Illustrious",
            trained_words=("mineru",),
            description=None,
            version_description=None,
            tags=("character",),
            creator_username=None,
            creator_image=None,
            nsfw=False,
            nsfw_level="None",
            availability=None,
            files=(),
            images=(),
            stats={},
            model_page_url=(
                f"https://civitai.com/models/{model_id}"
                f"?modelVersionId={model_version_id}"
            ),
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
            variants=(
                ThumbnailVariant(
                    size=128,
                    storage_key=resolved_storage_key,
                    width=85,
                    height=128,
                    content_format="sqthumb-qimage-argb32-premultiplied",
                    byte_size=65536,
                ),
            ),
            downloaded_at="2026-04-14T12:00:00Z",
        ),
        thumbnail_status=ThumbnailSelectionStatus.SELECTED,
        updated_at="2026-04-14T12:00:00Z",
    )
