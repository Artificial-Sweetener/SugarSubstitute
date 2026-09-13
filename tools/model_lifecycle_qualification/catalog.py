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

"""Project disposable model files through the production catalog service."""

from __future__ import annotations

import hashlib
from pathlib import Path

from substitute.application.model_metadata import ModelCatalogService
from substitute.domain.model_metadata import (
    BackendCapabilities,
    BackendFingerprint,
    BackendFingerprintJob,
    BackendLocalPreview,
    BackendModelCatalogEntry,
    BackendModelFile,
    BackendModelSource,
    BackendSidecar,
    FingerprintStatus,
    JobStatus,
    ModelMetadataCacheRecord,
)


class FilesystemBackend:
    """Expose synthetic model files through the real catalog-service boundary."""

    def __init__(self, model_root: Path) -> None:
        """Bind backend discovery to one disposable model-kind folder."""

        self._model_root = model_root
        self.list_model_calls: list[tuple[tuple[str, ...], bool]] = []

    def get_capabilities(self) -> BackendCapabilities | None:
        """Return no optional capabilities for this catalog-only adapter."""

        return None

    def list_models(
        self,
        kinds: tuple[str, ...],
        *,
        refresh: bool = False,
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Project current synthetic files as Comfy-visible catalog entries."""

        self.list_model_calls.append((kinds, refresh))
        if "diffusion_models" not in kinds:
            return ()
        return tuple(
            self._entry(path)
            for path in sorted(self._model_root.rglob("*"))
            if path.is_file()
        )

    def refresh_fingerprints(
        self,
        entries: tuple[BackendModelCatalogEntry, ...],
    ) -> BackendFingerprintJob:
        """Return a completed unused job for the catalog protocol."""

        _ = entries
        return BackendFingerprintJob(
            job_id="unused",
            status=JobStatus.COMPLETE,
            entries=(),
        )

    def get_fingerprint_job(self, job_id: str) -> BackendFingerprintJob | None:
        """Return no unused fingerprint job."""

        _ = job_id
        return None

    def _entry(self, path: Path) -> BackendModelCatalogEntry:
        """Build one exact backend catalog entry from a synthetic model file."""

        relative_path = path.relative_to(self._model_root).as_posix()
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        return BackendModelCatalogEntry(
            schema_version=1,
            target_id=f"synthetic-{relative_path}",
            kind="diffusion_models",
            value=relative_path,
            display_name=path.stem,
            source=BackendModelSource(
                root_id="synthetic-diffusion-models",
                relative_path=relative_path,
            ),
            file=BackendModelFile(
                extension=path.suffix,
                size_bytes=len(payload),
                modified_at="2026-09-13T00:00:00+00:00",
                created_at=None,
            ),
            fingerprint=BackendFingerprint(
                status=FingerprintStatus.READY,
                sha256=digest,
                source="synthetic-qualification",
                computed_at="2026-09-13T00:00:00+00:00",
                error=None,
            ),
            sidecar=BackendSidecar(
                found=False,
                model_id=None,
                model_version_id=None,
                sha256=None,
                activation_text=None,
                description=None,
                base_model="Anima",
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


class _EmptyMetadataCatalog:
    """Return no optional provider metadata around filesystem-backed models."""

    def list_records(
        self,
        *,
        kind: str | None = None,
    ) -> tuple[ModelMetadataCacheRecord, ...]:
        """Return an empty metadata projection for every model kind."""

        _ = kind
        return ()


def new_filesystem_catalog(
    model_root: Path,
) -> tuple[ModelCatalogService, FilesystemBackend]:
    """Construct fresh production catalog ownership for one synthetic root."""

    backend = FilesystemBackend(model_root)
    return (
        ModelCatalogService(
            backend=backend,
            metadata_catalog=_EmptyMetadataCatalog(),
        ),
        backend,
    )


__all__ = ["FilesystemBackend", "new_filesystem_catalog"]
