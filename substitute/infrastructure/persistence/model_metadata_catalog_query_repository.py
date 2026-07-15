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

"""Read normalized model metadata cache records from JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from substitute.domain.common import JsonObject
from substitute.domain.model_metadata import (
    CivitaiFile,
    CivitaiImage,
    CivitaiModelVersion,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailSelectionStatus,
    ThumbnailStoreResult,
    ThumbnailVariant,
    STANDARD_THUMBNAIL_ROLE,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger(
    "infrastructure.persistence.model_metadata_catalog_query_repository"
)


class JsonModelMetadataCatalogQueryRepository:
    """Read cached model metadata records from the model metadata catalog."""

    def __init__(self, model_metadata_root: Path) -> None:
        """Store resolved catalog paths used for metadata reads."""

        self._root = model_metadata_root.resolve()
        self._catalog_dir = self._root / "catalog"
        self._index_path = self._catalog_dir / "index.json"

    def list_records(
        self,
        *,
        kind: str | None = None,
    ) -> tuple[ModelMetadataCacheRecord, ...]:
        """Return cached metadata records, optionally filtered by model kind."""

        index_payload = self._read_json(self._index_path)
        if index_payload is None:
            return ()
        raw_records = index_payload.get("records")
        if not isinstance(raw_records, dict):
            log_warning(_LOGGER, "Metadata catalog index has invalid records shape")
            return ()

        records: list[ModelMetadataCacheRecord] = []
        for raw_entry in raw_records.values():
            if not isinstance(raw_entry, dict):
                continue
            if kind is not None and raw_entry.get("kind") != kind:
                continue
            record_path = self._record_path_from_index_entry(
                cast(JsonObject, raw_entry)
            )
            if record_path is None:
                continue
            record_payload = self._read_json(record_path)
            if record_payload is None:
                continue
            record = _cache_record_from_json(record_payload)
            if record is None:
                log_warning(
                    _LOGGER,
                    "Skipped invalid metadata cache record",
                    path=record_path,
                )
                continue
            if kind is None or record.local.kind == kind:
                records.append(record)
        return tuple(records)

    def recipe_hash_revision(self, *, kind: str | None = None) -> tuple[str, int, int]:
        """Return a cheap revision token for recipe hash index invalidation."""

        if not self._index_path.exists():
            return ("missing", 0, 0)
        stat = self._index_path.stat()
        index_payload = self._read_json(self._index_path)
        if index_payload is None:
            return ("invalid", stat.st_mtime_ns, stat.st_size)
        raw_records = index_payload.get("records")
        if not isinstance(raw_records, dict):
            return ("invalid-records", stat.st_mtime_ns, stat.st_size)
        if kind is None:
            return ("all", stat.st_mtime_ns, len(raw_records))
        matching_count = sum(
            1
            for raw_entry in raw_records.values()
            if isinstance(raw_entry, dict) and raw_entry.get("kind") == kind
        )
        return (kind, stat.st_mtime_ns, matching_count)

    def _record_path_from_index_entry(self, entry: JsonObject) -> Path | None:
        """Return a safe absolute record path from one catalog index entry."""

        raw_record_path = entry.get("recordPath")
        if not isinstance(raw_record_path, str) or not raw_record_path:
            return None
        record_path = (self._catalog_dir / raw_record_path).resolve()
        if (
            record_path != self._catalog_dir
            and self._catalog_dir not in record_path.parents
        ):
            log_warning(
                _LOGGER,
                "Metadata catalog record path escapes catalog root",
                record_path=raw_record_path,
            )
            return None
        return record_path

    def _read_json(self, path: Path) -> JsonObject | None:
        """Read one JSON object from disk, returning ``None`` on cache miss or damage."""

        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to read metadata cache JSON",
                path=path,
                error=repr(error),
            )
            return None
        return payload if isinstance(payload, dict) else None


def _cache_record_from_json(payload: JsonObject) -> ModelMetadataCacheRecord | None:
    """Parse one persisted metadata cache record from JSON."""

    local_payload = payload.get("local")
    if not isinstance(local_payload, dict):
        return None
    local = _local_evidence_from_json(cast(JsonObject, local_payload))
    if local is None:
        return None

    schema_version = _int_or_none(payload.get("schemaVersion"))
    provider_status = payload.get("providerStatus")
    thumbnail_status = payload.get("thumbnailStatus")
    updated_at = payload.get("updatedAt")
    if (
        schema_version is None
        or not isinstance(provider_status, str)
        or not isinstance(thumbnail_status, str)
        or not isinstance(updated_at, str)
    ):
        return None

    try:
        parsed_thumbnail_status = ThumbnailSelectionStatus(thumbnail_status)
    except ValueError:
        return None

    provider_payload = payload.get("provider")
    provider = (
        None
        if provider_payload is None
        else _provider_from_json(cast(JsonObject, provider_payload))
        if isinstance(provider_payload, dict)
        else None
    )
    if provider_payload is not None and provider is None:
        return None

    thumbnail_payload = payload.get("thumbnail")
    thumbnail = (
        None
        if thumbnail_payload is None
        else _thumbnail_from_json(cast(JsonObject, thumbnail_payload))
        if isinstance(thumbnail_payload, dict)
        else None
    )
    if thumbnail_payload is not None and thumbnail is None:
        return None

    return ModelMetadataCacheRecord(
        schema_version=schema_version,
        local=local,
        provider=provider,
        provider_status=provider_status,
        thumbnail=thumbnail,
        thumbnail_status=parsed_thumbnail_status,
        updated_at=updated_at,
    )


def _local_evidence_from_json(payload: JsonObject) -> LocalModelEvidence | None:
    """Parse local model evidence from one JSON payload."""

    target_id = payload.get("targetId")
    root_id = payload.get("rootId")
    relative_path = payload.get("relativePath")
    kind = payload.get("kind")
    value = payload.get("value")
    display_name = payload.get("displayName")
    modified_at = payload.get("modifiedAt")
    sha256 = payload.get("sha256")
    size_bytes = _int_or_none(payload.get("sizeBytes"))
    if (
        not isinstance(target_id, str)
        or not isinstance(root_id, str)
        or not isinstance(relative_path, str)
        or not isinstance(kind, str)
        or not isinstance(value, str)
        or not isinstance(display_name, str)
        or not isinstance(modified_at, str)
        or not isinstance(sha256, str)
        or size_bytes is None
    ):
        return None
    return LocalModelEvidence(
        target_id=target_id,
        root_id=root_id,
        relative_path=relative_path,
        kind=kind,
        value=value,
        display_name=display_name,
        size_bytes=size_bytes,
        modified_at=modified_at,
        sha256=sha256,
    )


def _provider_from_json(payload: JsonObject) -> CivitaiModelVersion | None:
    """Parse normalized CivitAI provider metadata from JSON."""

    model_id = _int_or_none(payload.get("modelId"))
    model_version_id = _int_or_none(payload.get("modelVersionId"))
    model_name = payload.get("modelName")
    version_name = payload.get("versionName")
    fetched_at = payload.get("fetchedAt")
    model_page_url = payload.get("modelPageUrl")
    source_url = payload.get("sourceUrl")
    if (
        model_id is None
        or model_version_id is None
        or not isinstance(model_name, str)
        or not isinstance(version_name, str)
        or not isinstance(fetched_at, str)
        or not isinstance(model_page_url, str)
        or not isinstance(source_url, str)
    ):
        return None

    creator = payload.get("creator")
    creator_username = None
    creator_image = None
    if isinstance(creator, dict):
        creator_username = _optional_str(creator.get("username"))
        creator_image = _optional_str(creator.get("image"))

    return CivitaiModelVersion(
        model_id=model_id,
        model_version_id=model_version_id,
        model_name=model_name,
        model_type=_optional_str(payload.get("modelType")),
        version_name=version_name,
        base_model=_optional_str(payload.get("baseModel")),
        trained_words=_str_tuple(payload.get("trainedWords")),
        description=_optional_str(payload.get("description")),
        version_description=_optional_str(payload.get("versionDescription")),
        tags=_str_tuple(payload.get("tags")),
        creator_username=creator_username,
        creator_image=creator_image,
        nsfw=_optional_bool(payload.get("nsfw")),
        nsfw_level=_optional_str_int(payload.get("nsfwLevel")),
        availability=_optional_str(payload.get("availability")),
        files=_files_from_json(payload.get("files")),
        images=_images_from_json(payload.get("images")),
        stats=cast(
            JsonObject,
            payload.get("stats") if isinstance(payload.get("stats"), dict) else {},
        ),
        model_page_url=model_page_url,
        source_url=source_url,
        fetched_at=fetched_at,
        raw_provider_payload=cast(
            JsonObject,
            payload.get("rawProviderPayload")
            if isinstance(payload.get("rawProviderPayload"), dict)
            else {},
        ),
    )


def _files_from_json(value: object) -> tuple[CivitaiFile, ...]:
    """Parse CivitAI file metadata from JSON."""

    if not isinstance(value, list):
        return ()
    files: list[CivitaiFile] = []
    for raw_file in value:
        if not isinstance(raw_file, dict):
            continue
        name = raw_file.get("name")
        hashes = raw_file.get("hashes")
        metadata = raw_file.get("metadata")
        if not isinstance(name, str):
            continue
        files.append(
            CivitaiFile(
                file_id=_int_or_none(raw_file.get("id")),
                name=name,
                size_kb=_float_or_none(raw_file.get("sizeKB")),
                file_type=_optional_str(raw_file.get("type")),
                download_url=_optional_str(raw_file.get("downloadUrl")),
                pickle_scan_result=_optional_str(raw_file.get("pickleScanResult")),
                virus_scan_result=_optional_str(raw_file.get("virusScanResult")),
                primary=bool(raw_file.get("primary")),
                hashes=cast(JsonObject, hashes if isinstance(hashes, dict) else {}),
                metadata=cast(
                    JsonObject,
                    metadata if isinstance(metadata, dict) else {},
                ),
            )
        )
    return tuple(files)


def _images_from_json(value: object) -> tuple[CivitaiImage, ...]:
    """Parse CivitAI image metadata from JSON."""

    if not isinstance(value, list):
        return ()
    images: list[CivitaiImage] = []
    for raw_image in value:
        if not isinstance(raw_image, dict):
            continue
        url = raw_image.get("url")
        if not isinstance(url, str):
            continue
        images.append(
            CivitaiImage(
                image_id=_int_or_none(raw_image.get("id")),
                url=url,
                image_type=_optional_str(raw_image.get("type")),
                nsfw=_optional_bool(raw_image.get("nsfw")),
                nsfw_level=raw_image.get("nsfwLevel"),
                width=_int_or_none(raw_image.get("width")),
                height=_int_or_none(raw_image.get("height")),
                meta=cast(
                    JsonObject | None,
                    raw_image.get("meta")
                    if isinstance(raw_image.get("meta"), dict)
                    else None,
                ),
            )
        )
    return tuple(images)


def _thumbnail_from_json(payload: JsonObject) -> ThumbnailStoreResult | None:
    """Parse cached thumbnail metadata from JSON."""

    required = (
        "source",
        "selectionPolicy",
        "sourceImageUrl",
        "downloadedAt",
    )
    if not all(isinstance(payload.get(key), str) for key in required):
        return None
    variants = _thumbnail_variants_from_json(payload.get("variants"))
    if not variants:
        return None
    return ThumbnailStoreResult(
        source=cast(str, payload["source"]),
        selection_policy=cast(str, payload["selectionPolicy"]),
        source_image_url=cast(str, payload["sourceImageUrl"]),
        source_image_id=_int_or_none(payload.get("sourceImageId")),
        nsfw=_optional_bool(payload.get("nsfw")),
        nsfw_level=_optional_str_int(payload.get("nsfwLevel")),
        source_width=_int_or_none(payload.get("sourceWidth")),
        source_height=_int_or_none(payload.get("sourceHeight")),
        variants=variants,
        downloaded_at=cast(str, payload["downloadedAt"]),
    )


def _thumbnail_variants_from_json(value: object) -> tuple[ThumbnailVariant, ...]:
    """Parse prepared thumbnail variant metadata from JSON."""

    if not isinstance(value, list):
        return ()
    variants: list[ThumbnailVariant] = []
    for raw_variant in value:
        if not isinstance(raw_variant, dict):
            continue
        size = _int_or_none(raw_variant.get("size"))
        storage_key = raw_variant.get("storageKey") or raw_variant.get("cachedPath")
        width = _int_or_none(raw_variant.get("width"))
        height = _int_or_none(raw_variant.get("height"))
        content_format = raw_variant.get("contentFormat")
        byte_size = _int_or_none(raw_variant.get("byteSize"))
        role = raw_variant.get("role")
        if (
            size is None
            or not isinstance(storage_key, str)
            or width is None
            or height is None
            or not isinstance(content_format, str)
            or byte_size is None
        ):
            continue
        variants.append(
            ThumbnailVariant(
                size=size,
                storage_key=storage_key,
                width=width,
                height=height,
                content_format=content_format,
                byte_size=byte_size,
                role=role if isinstance(role, str) else STANDARD_THUMBNAIL_ROLE,
            )
        )
    return tuple(variants)


def _int_or_none(value: object) -> int | None:
    """Return an integer parsed from one JSON value when possible."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _float_or_none(value: object) -> float | None:
    """Return a float parsed from one JSON value when possible."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _optional_str(value: object) -> str | None:
    """Return a string only when the supplied JSON value is a string."""

    return value if isinstance(value, str) else None


def _optional_bool(value: object) -> bool | None:
    """Return a bool only when the supplied JSON value is a bool."""

    return value if isinstance(value, bool) else None


def _optional_str_int(value: object) -> str | int | None:
    """Return a string or integer only when the supplied JSON value is supported."""

    if isinstance(value, bool):
        return None
    return value if isinstance(value, str | int) else None


def _str_tuple(value: object) -> tuple[str, ...]:
    """Return all string entries from one JSON list value."""

    if not isinstance(value, list):
        return ()
    return tuple(entry for entry in value if isinstance(entry, str))


__all__ = ["JsonModelMetadataCatalogQueryRepository"]
