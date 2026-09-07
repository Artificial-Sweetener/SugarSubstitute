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

"""Verify queued payloads record exact metadata-backed model usage."""

from __future__ import annotations

from pathlib import Path

from substitute.application.model_metadata import ModelCatalogItem
from substitute.application.model_updates import GenerationModelUsageRecorder
from sugarsubstitute_shared.model_discovery import ModelArtifactKind


class _Catalog:
    """Return models by backend kind."""

    def __init__(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Store catalog rows."""

        self._items = items

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return rows matching one requested kind."""

        return tuple(item for item in self._items if item.kind == kind)


class _Usage:
    """Record exact usage calls."""

    def __init__(self) -> None:
        """Initialize no calls."""

        self.calls: list[dict[str, object]] = []

    def record_usage(self, **kwargs: object) -> object:
        """Capture one model identity."""

        self.calls.append(kwargs)
        return object()


def _item(
    *,
    kind: str,
    backend_value: str,
    sha256: str | None,
    model_id: str | None = "4",
    version_id: str | None = "5",
) -> ModelCatalogItem:
    """Build a minimal metadata-backed catalog row."""

    return ModelCatalogItem(
        kind=kind,
        display_name=backend_value,
        display_subtitle=None,
        backend_value=backend_value,
        relative_path=backend_value,
        folder="",
        basename=Path(backend_value).stem,
        extension=Path(backend_value).suffix,
        thumbnail_variants=(),
        base_model="SDXL",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=backend_value,
        collision_count=1,
        has_collision=False,
        search_text=backend_value,
        provider_model_id=model_id,
        provider_model_version_id=version_id,
        sha256=sha256,
    )


def test_nested_payload_records_distinct_exact_catalog_models() -> None:
    """Only values present in the successfully queued payload should count as usage."""

    shared_hash = "a" * 64
    checkpoint = _item(
        kind="checkpoints",
        backend_value="models/base.safetensors",
        sha256=shared_hash,
    )
    duplicate_hash = _item(
        kind="diffusion_models",
        backend_value="models/diffusion.safetensors",
        sha256=shared_hash,
    )
    lora = _item(
        kind="loras",
        backend_value="styles/detail.safetensors",
        sha256="b" * 64,
    )
    unused = _item(
        kind="vae",
        backend_value="unused.safetensors",
        sha256="c" * 64,
    )
    usage = _Usage()
    recorder = GenerationModelUsageRecorder(
        catalog=_Catalog((checkpoint, duplicate_hash, lora, unused)),
        usage=usage,
    )

    count = recorder.record_queued_payload(
        {
            "nodes": {
                "1": {"inputs": {"ckpt_name": checkpoint.backend_value}},
                "2": {"inputs": {"lora_name": [lora.backend_value, 1.0]}},
                "3": {"inputs": {"model": duplicate_hash.backend_value}},
            }
        }
    )

    assert count == 2
    assert {call["sha256"] for call in usage.calls} == {"a" * 64, "b" * 64}
    assert {call["artifact_kind"] for call in usage.calls} == {
        ModelArtifactKind.CHECKPOINTS,
        ModelArtifactKind.LORAS,
    }


def test_missing_hash_and_malformed_provider_ids_fail_closed() -> None:
    """Unfingerprinted rows must not become usage; malformed IDs become unknown."""

    missing_hash = _item(
        kind="checkpoints",
        backend_value="missing.safetensors",
        sha256=None,
    )
    valid = _item(
        kind="loras",
        backend_value="known.safetensors",
        sha256="d" * 64,
        model_id="not-an-id",
        version_id="-2",
    )
    usage = _Usage()
    recorder = GenerationModelUsageRecorder(
        catalog=_Catalog((missing_hash, valid)),
        usage=usage,
    )

    assert (
        recorder.record_queued_payload(
            {"missing": missing_hash.backend_value, "known": valid.backend_value}
        )
        == 1
    )
    assert usage.calls[0]["model_id"] is None
    assert usage.calls[0]["version_id"] is None
