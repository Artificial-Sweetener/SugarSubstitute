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

"""Persist normalized model metadata cache records as JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
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
)
from substitute.domain.model_metadata.thumbnail_policy import FirstSfwThumbnailPolicy
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.model_metadata_catalog_store")
_THUMBNAIL_POLICY_VERSION = 3


class JsonModelMetadataCatalogStore:
    """Store model metadata catalog records under a model metadata root."""

    def __init__(self, model_metadata_root: Path) -> None:
        """Initialize the store and create required catalog directories."""

        self._root = model_metadata_root.resolve()
        self._catalog_dir = self._root / "catalog"
        self._provider_dir = self._catalog_dir / "civitai"
        self._fingerprints_dir = self._root / "fingerprints"
        self._index_path = self._catalog_dir / "index.json"
        self._fingerprint_index_path = self._fingerprints_dir / "index.json"
        self._provider_dir.mkdir(parents=True, exist_ok=True)
        self._fingerprints_dir.mkdir(parents=True, exist_ok=True)

    def is_fresh(self, evidence: LocalModelEvidence) -> bool:
        """Return whether persisted metadata matches the local model evidence."""

        payload = self._read_json(self._record_path(evidence.sha256))
        if payload is None:
            return False
        local_payload = payload.get("local")
        if not isinstance(local_payload, dict):
            return False
        if not _local_evidence_payload_matches(
            evidence, cast(JsonObject, local_payload)
        ):
            return False
        return _cached_thumbnail_policy_is_current(payload)

    def record_for_sha256(self, sha256: str) -> ModelMetadataCacheRecord | None:
        """Return one cached metadata record by SHA256 when available."""

        payload = self._read_json(self._record_path(sha256))
        if payload is None:
            return None
        return _cache_record_from_json(payload)

    def save_record(self, record: ModelMetadataCacheRecord) -> None:
        """Persist one enriched provider record and update indexes."""

        payload = _cache_record_to_json(record)
        self._write_json_atomic(self._record_path(record.local.sha256), payload)
        self._update_indexes(record.local, record.provider_status, record.updated_at)

    def save_not_found(self, evidence: LocalModelEvidence, *, fetched_at: str) -> None:
        """Persist a provider-not-found result for one local model."""

        payload: JsonObject = {
            "schemaVersion": 1,
            "local": evidence.to_json(),
            "provider": None,
            "providerStatus": "not-found",
            "thumbnail": None,
            "thumbnailStatus": ThumbnailSelectionStatus.NO_SFW_IMAGE.value,
            "updatedAt": fetched_at,
        }
        self._write_json_atomic(self._record_path(evidence.sha256), payload)
        self._update_indexes(evidence, "not-found", fetched_at)

    def _record_path(self, sha256: str) -> Path:
        """Return the provider metadata record path for one SHA256 key."""

        return self._provider_dir / f"{sha256.upper()}.json"

    def _update_indexes(
        self,
        evidence: LocalModelEvidence,
        provider_status: str,
        updated_at: str,
    ) -> None:
        """Update lightweight lookup indexes after writing a provider record."""

        catalog_index = self._read_json(self._index_path) or {}
        records = catalog_index.get("records")
        if not isinstance(records, dict):
            records = {}
        records[evidence.sha256] = {
            "provider": "civitai",
            "providerStatus": provider_status,
            "relativePath": evidence.relative_path,
            "kind": evidence.kind,
            "displayName": evidence.display_name,
            "updatedAt": updated_at,
            "recordPath": f"civitai/{evidence.sha256}.json",
        }
        catalog_index = {"schemaVersion": 1, "records": records}
        self._write_json_atomic(self._index_path, catalog_index)

        fingerprint_index = self._read_json(self._fingerprint_index_path) or {}
        fingerprints = fingerprint_index.get("fingerprints")
        if not isinstance(fingerprints, dict):
            fingerprints = {}
        fingerprints[evidence.sha256] = evidence.to_json()
        fingerprint_index = {"schemaVersion": 1, "fingerprints": fingerprints}
        self._write_json_atomic(self._fingerprint_index_path, fingerprint_index)

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
                error=error,
            )
            return None
        return payload if isinstance(payload, dict) else None

    def _write_json_atomic(self, path: Path, payload: JsonObject) -> None:
        """Write one JSON object by replacing a same-directory temporary file."""

        _ensure_child_path(self._root, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temporary_path.replace(path)


def _cache_record_to_json(record: ModelMetadataCacheRecord) -> JsonObject:
    """Convert one cache record into a stable JSON payload."""

    return {
        "schemaVersion": record.schema_version,
        "local": record.local.to_json(),
        "provider": _provider_to_json(record.provider),
        "providerStatus": record.provider_status,
        "thumbnail": record.thumbnail.to_json() if record.thumbnail else None,
        "thumbnailPolicy": FirstSfwThumbnailPolicy.selection_policy,
        "thumbnailPolicyVersion": _THUMBNAIL_POLICY_VERSION,
        "thumbnailStatus": record.thumbnail_status.value,
        "updatedAt": record.updated_at,
    }


def _cache_record_from_json(payload: JsonObject) -> ModelMetadataCacheRecord | None:
    """Return one cache record from a JSON payload, or ``None`` when invalid."""

    local_payload = payload.get("local")
    if not isinstance(local_payload, dict):
        return None
    local = _local_evidence_from_json(cast(JsonObject, local_payload))
    if local is None:
        return None
    provider_payload = payload.get("provider")
    provider = (
        _provider_from_json(cast(JsonObject, provider_payload))
        if isinstance(provider_payload, dict)
        else None
    )
    thumbnail_payload = payload.get("thumbnail")
    thumbnail = (
        _thumbnail_from_json(cast(JsonObject, thumbnail_payload))
        if isinstance(thumbnail_payload, dict)
        else None
    )
    thumbnail_status_value = payload.get("thumbnailStatus")
    try:
        thumbnail_status = ThumbnailSelectionStatus(str(thumbnail_status_value))
    except ValueError:
        thumbnail_status = ThumbnailSelectionStatus.NO_SFW_IMAGE
    return ModelMetadataCacheRecord(
        schema_version=_optional_int(payload.get("schemaVersion")) or 1,
        local=local,
        provider=provider,
        provider_status=str(payload.get("providerStatus") or "stale"),
        thumbnail=thumbnail,
        thumbnail_status=thumbnail_status,
        updated_at=str(payload.get("updatedAt") or ""),
    )


def _local_evidence_from_json(payload: JsonObject) -> LocalModelEvidence | None:
    """Return local model evidence from a JSON object when complete."""

    required = (
        "targetId",
        "rootId",
        "relativePath",
        "kind",
        "backendValue",
        "displayName",
        "sizeBytes",
        "modifiedAt",
        "sha256",
    )
    if any(key not in payload for key in required):
        return None
    return LocalModelEvidence(
        target_id=str(payload["targetId"]),
        root_id=str(payload["rootId"]),
        relative_path=str(payload["relativePath"]),
        kind=str(payload["kind"]),
        value=str(payload["backendValue"]),
        display_name=str(payload["displayName"]),
        size_bytes=_optional_int(payload["sizeBytes"]) or 0,
        modified_at=str(payload["modifiedAt"]),
        sha256=str(payload["sha256"]).upper(),
    )


def _provider_from_json(payload: JsonObject) -> CivitaiModelVersion:
    """Return normalized CivitAI provider metadata from JSON."""

    creator = payload.get("creator")
    creator_payload = creator if isinstance(creator, dict) else {}
    return CivitaiModelVersion(
        model_id=_optional_int(payload.get("modelId")) or 0,
        model_version_id=_optional_int(payload.get("modelVersionId")) or 0,
        model_name=str(payload.get("modelName") or ""),
        model_type=_optional_str(payload.get("modelType")),
        version_name=str(payload.get("versionName") or ""),
        base_model=_optional_str(payload.get("baseModel")),
        trained_words=_str_tuple(payload.get("trainedWords")),
        description=_optional_str(payload.get("description")),
        version_description=_optional_str(payload.get("versionDescription")),
        tags=_str_tuple(payload.get("tags")),
        creator_username=_optional_str(creator_payload.get("username")),
        creator_image=_optional_str(creator_payload.get("image")),
        nsfw=_optional_bool(payload.get("nsfw")),
        nsfw_level=_optional_str_int(payload.get("nsfwLevel")),
        availability=_optional_str(payload.get("availability")),
        files=tuple(
            _file_from_json(item) for item in _json_object_list(payload.get("files"))
        ),
        images=tuple(
            _image_from_json(item) for item in _json_object_list(payload.get("images"))
        ),
        stats=_json_object(payload.get("stats")),
        model_page_url=str(payload.get("modelPageUrl") or ""),
        source_url=str(payload.get("sourceUrl") or ""),
        fetched_at=str(payload.get("fetchedAt") or ""),
        raw_provider_payload=_json_object(payload.get("rawProviderPayload")),
    )


def _file_from_json(payload: JsonObject) -> CivitaiFile:
    """Return one CivitAI file metadata record from JSON."""

    return CivitaiFile(
        file_id=_optional_int(payload.get("id")),
        name=str(payload.get("name") or ""),
        size_kb=_optional_float(payload.get("sizeKB")),
        file_type=_optional_str(payload.get("type")),
        download_url=_optional_str(payload.get("downloadUrl")),
        pickle_scan_result=_optional_str(payload.get("pickleScanResult")),
        virus_scan_result=_optional_str(payload.get("virusScanResult")),
        primary=bool(payload.get("primary")),
        hashes=_json_object(payload.get("hashes")),
        metadata=_json_object(payload.get("metadata")),
    )


def _image_from_json(payload: JsonObject) -> CivitaiImage:
    """Return one CivitAI image metadata record from JSON."""

    return CivitaiImage(
        image_id=_optional_int(payload.get("id")),
        url=str(payload.get("url") or ""),
        image_type=_optional_str(payload.get("type")),
        nsfw=_optional_bool(payload.get("nsfw")),
        nsfw_level=_optional_str_int(payload.get("nsfwLevel")),
        width=_optional_int(payload.get("width")),
        height=_optional_int(payload.get("height")),
        meta=(
            cast(JsonObject, payload.get("meta"))
            if isinstance(payload.get("meta"), dict)
            else None
        ),
    )


def _thumbnail_from_json(payload: JsonObject) -> ThumbnailStoreResult:
    """Return cached thumbnail metadata from JSON."""

    return ThumbnailStoreResult(
        source=str(payload.get("source") or ""),
        selection_policy=str(payload.get("selectionPolicy") or ""),
        source_image_url=str(payload.get("sourceImageUrl") or ""),
        source_image_id=_optional_int(payload.get("sourceImageId")),
        nsfw=_optional_bool(payload.get("nsfw")),
        nsfw_level=_optional_str_int(payload.get("nsfwLevel")),
        source_width=_optional_int(payload.get("sourceWidth")),
        source_height=_optional_int(payload.get("sourceHeight")),
        variants=tuple(
            _thumbnail_variant_from_json(item)
            for item in _json_object_list(payload.get("variants"))
        ),
        downloaded_at=str(payload.get("downloadedAt") or ""),
    )


def _thumbnail_variant_from_json(payload: JsonObject) -> ThumbnailVariant:
    """Return one thumbnail variant from JSON."""

    return ThumbnailVariant(
        storage_key=str(payload.get("storageKey") or ""),
        role=str(payload.get("role") or "standard"),
        size=_optional_int(payload.get("size")) or 0,
        width=_optional_int(payload.get("width")) or 0,
        height=_optional_int(payload.get("height")) or 0,
        content_format=str(payload.get("contentFormat") or ""),
        byte_size=_optional_int(payload.get("byteSize")) or 0,
    )


def _provider_to_json(provider: CivitaiModelVersion | None) -> JsonObject | None:
    """Convert normalized CivitAI provider metadata into JSON."""

    if provider is None:
        return None
    return {
        "provider": "civitai",
        "modelId": provider.model_id,
        "modelVersionId": provider.model_version_id,
        "modelName": provider.model_name,
        "modelType": provider.model_type,
        "versionName": provider.version_name,
        "baseModel": provider.base_model,
        "trainedWords": list(provider.trained_words),
        "description": provider.description,
        "versionDescription": provider.version_description,
        "tags": list(provider.tags),
        "creator": {
            "username": provider.creator_username,
            "image": provider.creator_image,
        },
        "nsfw": provider.nsfw,
        "nsfwLevel": provider.nsfw_level,
        "availability": provider.availability,
        "files": [_file_to_json(file) for file in provider.files],
        "images": [_image_to_json(image) for image in provider.images],
        "stats": provider.stats,
        "modelPageUrl": provider.model_page_url,
        "sourceUrl": provider.source_url,
        "fetchedAt": provider.fetched_at,
        "rawProviderPayload": provider.raw_provider_payload,
    }


def _file_to_json(file: CivitaiFile) -> JsonObject:
    """Convert one CivitAI file metadata record into JSON."""

    return {
        "id": file.file_id,
        "name": file.name,
        "sizeKB": file.size_kb,
        "primary": file.primary,
        "hashes": file.hashes,
        "metadata": file.metadata,
    }


def _image_to_json(image: CivitaiImage) -> JsonObject:
    """Convert one CivitAI image metadata record into JSON."""

    return {
        "id": image.image_id,
        "url": image.url,
        "type": image.image_type,
        "nsfw": image.nsfw,
        "nsfwLevel": image.nsfw_level,
        "width": image.width,
        "height": image.height,
        "meta": image.meta,
    }


def _local_evidence_payload_matches(
    evidence: LocalModelEvidence,
    payload: JsonObject,
) -> bool:
    """Return whether one JSON local-evidence payload matches the given evidence."""

    return all(payload.get(key) == value for key, value in evidence.to_json().items())


def _cached_thumbnail_policy_is_current(payload: JsonObject) -> bool:
    """Return whether an existing found-provider record used the current policy."""

    if payload.get("providerStatus") != "found":
        return True
    thumbnail_payload = payload.get("thumbnail")
    if isinstance(thumbnail_payload, dict) and not isinstance(
        thumbnail_payload.get("variants"), list
    ):
        return False
    return (
        payload.get("thumbnailPolicy") == FirstSfwThumbnailPolicy.selection_policy
        and payload.get("thumbnailPolicyVersion") == _THUMBNAIL_POLICY_VERSION
    )


def _ensure_child_path(root: Path, path: Path) -> None:
    """Fail if a write path would escape the configured metadata root."""

    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"Metadata cache path escapes root: {path}")


def _optional_int(value: object) -> int | None:
    """Return an integer from a JSON scalar when present."""

    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return None


def _optional_float(value: object) -> float | None:
    """Return a float from a JSON scalar when present."""

    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return None


def _optional_bool(value: object) -> bool | None:
    """Return an optional boolean from a JSON scalar."""

    return value if isinstance(value, bool) else None


def _optional_str(value: object) -> str | None:
    """Return an optional non-empty string from a JSON scalar."""

    return value if isinstance(value, str) and value else None


def _optional_str_int(value: object) -> str | int | None:
    """Return an optional string or integer from a JSON scalar."""

    if isinstance(value, bool):
        return None
    return value if isinstance(value, str | int) else None


def _str_tuple(value: object) -> tuple[str, ...]:
    """Return a string tuple from a JSON array."""

    return (
        tuple(item for item in value if isinstance(item, str))
        if isinstance(value, list)
        else ()
    )


def _json_object(value: object) -> JsonObject:
    """Return a JSON object from a decoded JSON value."""

    return cast(JsonObject, value if isinstance(value, dict) else {})


def _json_object_list(value: object) -> tuple[JsonObject, ...]:
    """Return JSON objects from a decoded JSON array."""

    if not isinstance(value, list):
        return ()
    return tuple(cast(JsonObject, item) for item in value if isinstance(item, dict))


__all__ = ["JsonModelMetadataCatalogStore"]
