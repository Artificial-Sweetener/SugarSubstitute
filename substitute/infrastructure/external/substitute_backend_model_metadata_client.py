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

"""HTTP client for Substitute BackEnd model metadata routes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlencode

from substitute.domain.common import JsonObject
from substitute.domain.model_metadata import (
    BackendCapabilities,
    BackendCubeLibraryCapabilities,
    BackendFingerprint,
    BackendFingerprintJob,
    BackendFingerprintJobEntry,
    BackendHashLookupMatch,
    BackendHashLookupResult,
    BackendLocalPreview,
    BackendModelCatalogEntry,
    BackendModelDownloadJob,
    BackendModelDownloadResult,
    BackendModelFile,
    BackendModelSource,
    BackendSidecar,
    BackendSugarCompileCapabilities,
    BackendModelCatalogChangeEvent,
    BackendHashLookupStatus,
    FingerprintStatus,
    JobStatus,
    ModelDownloadStatus,
    parse_backend_model_catalog_change_event,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import (
    default_http_get,
    default_http_post,
    is_request_exception,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("infrastructure.external.substitute_backend_model_metadata_client")
HttpGet = Callable[..., Any]
HttpPost = Callable[..., Any]


class SubstituteBackendModelMetadataClient:
    """Query Substitute BackEnd model metadata routes through Comfy's HTTP server."""

    def __init__(
        self,
        endpoint: ComfyEndpoint,
        *,
        http_get: HttpGet | None = None,
        http_post: HttpPost | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        """Initialize the client with endpoint and injectable HTTP transport."""

        self._endpoint = endpoint
        self._http_get = http_get or default_http_get
        self._http_post = http_post or default_http_post
        self._timeout_seconds = timeout_seconds
        self._warned_get_failure_endpoints: set[str] = set()

    def get_capabilities(self) -> BackendCapabilities | None:
        """Return backend capabilities or ``None`` when unavailable."""

        payload = self._get_json("/substitute/v1/capabilities")
        if payload is None:
            return None
        try:
            model_metadata = _read_object(payload, "modelMetadata")
            return BackendCapabilities(
                api_version=_read_int(payload, "apiVersion") or 0,
                model_metadata_schema_version=_read_int(model_metadata, "schemaVersion")
                or 0,
                supported_model_kinds=_read_str_tuple(
                    model_metadata, "supportedModelKinds"
                ),
                background_hashing=_read_bool(model_metadata, "backgroundHashing"),
                hash_lookup=_read_bool(model_metadata, "hashLookup"),
                local_preview_serving=_read_bool(model_metadata, "localPreviewServing"),
                sidecar_reading=_read_bool(model_metadata, "sidecarReading"),
                extension_version=_read_str(payload, "extensionVersion") or "",
                features=_read_str_tuple(payload, "features"),
                cube_library=_parse_cube_library_capabilities(
                    payload.get("cubeLibrary")
                ),
                sugar_compile=_parse_sugar_compile_capabilities(
                    payload.get("sugarCompile")
                ),
            )
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Substitute BackEnd capabilities payload",
                error=repr(error),
            )
            return None

    def list_models(
        self,
        kinds: tuple[str, ...],
        *,
        refresh: bool = False,
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Return Comfy-visible model catalog entries for requested kinds."""

        query_parts: list[tuple[str, str]] = [("kind", kind) for kind in kinds]
        if refresh:
            query_parts.append(("refresh", "1"))
        query = urlencode(query_parts)
        path = "/substitute/v1/models"
        if query:
            path = f"{path}?{query}"
        payload = self._get_json(path)
        if payload is None:
            if refresh:
                raise RuntimeError("Backend model catalog refresh failed.")
            return ()
        raw_models = payload.get("models")
        if not isinstance(raw_models, list):
            if refresh:
                raise RuntimeError(
                    "Backend model catalog refresh returned no models list."
                )
            log_warning(_LOGGER, "Invalid model catalog payload: models is not a list")
            return ()
        entries: list[BackendModelCatalogEntry] = []
        for raw_model in raw_models:
            if not isinstance(raw_model, dict):
                continue
            try:
                entries.append(_parse_model_catalog_entry(raw_model))
            except ValueError as error:
                log_warning(
                    _LOGGER,
                    "Skipped invalid backend model catalog entry",
                    error=repr(error),
                )
        return tuple(entries)

    def refresh_fingerprints(
        self, entries: tuple[BackendModelCatalogEntry, ...]
    ) -> BackendFingerprintJob:
        """Queue SHA256 fingerprint refresh for selected entries."""

        entries_payload: list[JsonObject] = [
            {
                "kind": entry.kind,
                "value": entry.value,
                "sizeBytes": entry.file.size_bytes,
                "modifiedAt": entry.file.modified_at,
            }
            for entry in entries
        ]
        body: JsonObject = {
            "entries": entries_payload,
        }
        payload = self._post_json("/substitute/v1/models/fingerprints/refresh", body)
        if payload is None:
            return BackendFingerprintJob(
                job_id="unavailable", status=JobStatus.FAILED, entries=()
            )
        try:
            return _parse_fingerprint_job(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid fingerprint refresh response",
                error=repr(error),
            )
            return BackendFingerprintJob(
                job_id="invalid", status=JobStatus.FAILED, entries=()
            )

    def get_fingerprint_job(self, job_id: str) -> BackendFingerprintJob | None:
        """Return the latest status for one backend fingerprint job."""

        payload = self._get_json(f"/substitute/v1/models/fingerprints/jobs/{job_id}")
        if payload is None:
            return None
        try:
            return _parse_fingerprint_job(payload)
        except ValueError as error:
            log_warning(_LOGGER, "Invalid fingerprint job response", error=repr(error))
            return None

    def get_latest_model_catalog_change(
        self,
    ) -> BackendModelCatalogChangeEvent | None:
        """Return the latest backend model catalog change for reconnect recovery."""

        payload = self._get_json("/substitute/v1/models/changes")
        if payload is None:
            return None
        latest_change = payload.get("latestChange")
        if latest_change is None:
            return None
        if not isinstance(latest_change, dict):
            log_warning(_LOGGER, "Invalid latest model catalog change payload")
            return None
        parsed = parse_backend_model_catalog_change_event(latest_change)
        if parsed is None:
            log_warning(_LOGGER, "Malformed latest model catalog change payload")
        return parsed

    def lookup_model_by_hash(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> BackendHashLookupResult | None:
        """Return backend local model matches for a SHA256 hash."""

        query = urlencode({"kind": kind})
        payload = self._get_json(
            f"/substitute/v1/models/by-hash/{sha256.upper()}?{query}"
        )
        if payload is None:
            return None
        try:
            return _parse_hash_lookup_result(payload)
        except ValueError as error:
            log_warning(_LOGGER, "Invalid hash lookup response", error=repr(error))
            return None

    def start_civitai_model_download(
        self,
        *,
        kind: str,
        sha256: str,
        download_url: str,
        file_name: str,
        file_type: str | None,
        metadata_format: str | None,
        pickle_scan_result: str | None,
        virus_scan_result: str | None,
        download_path_pattern: str,
        download_path_tokens: Mapping[str, str],
        api_key: str | None,
    ) -> BackendModelDownloadJob | None:
        """Queue a backend-owned CivitAI model download."""

        body: JsonObject = {
            "kind": kind,
            "sha256": sha256.upper(),
            "downloadUrl": download_url,
            "fileName": file_name,
            "fileType": file_type or "",
            "metadataFormat": metadata_format or "",
            "pickleScanResult": pickle_scan_result or "",
            "virusScanResult": virus_scan_result or "",
            "downloadPathPattern": download_path_pattern,
            "downloadPathTokens": dict(download_path_tokens),
        }
        if api_key:
            body["apiKey"] = api_key
        payload = self._post_json("/substitute/v1/models/downloads/civitai", body)
        if payload is None:
            return None
        try:
            return _parse_model_download_job(payload)
        except ValueError as error:
            log_warning(_LOGGER, "Invalid model download response", error=repr(error))
            return None

    def get_model_download_job(self, job_id: str) -> BackendModelDownloadJob | None:
        """Return a backend model download job by identifier."""

        payload = self._get_json(f"/substitute/v1/models/downloads/jobs/{job_id}")
        if payload is None:
            return None
        try:
            return _parse_model_download_job(payload)
        except ValueError as error:
            log_warning(
                _LOGGER, "Invalid model download job response", error=repr(error)
            )
            return None

    def cancel_model_download_job(self, job_id: str) -> BackendModelDownloadJob | None:
        """Request cancellation for one backend model download job."""

        payload = self._post_json(
            f"/substitute/v1/models/downloads/jobs/{job_id}/cancel",
            {},
        )
        if payload is None:
            return None
        try:
            return _parse_model_download_job(payload)
        except ValueError as error:
            log_warning(
                _LOGGER, "Invalid model download cancel response", error=repr(error)
            )
            return None

    def _get_json(self, path: str) -> JsonObject | None:
        """GET one backend route and return a JSON object on success.

        Expected backend startup outages warn once per endpoint, then fall back to
        debug logging until the endpoint recovers.
        """

        endpoint = self._url(path)
        try:
            response = self._http_get(endpoint, timeout=self._timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not _is_expected_http_error(error):
                raise
            log_context = {"endpoint": endpoint, "error": repr(error)}
            if endpoint in self._warned_get_failure_endpoints:
                log_debug(_LOGGER, "Substitute BackEnd GET failed", **log_context)
            else:
                self._warned_get_failure_endpoints.add(endpoint)
                log_warning(_LOGGER, "Substitute BackEnd GET failed", **log_context)
            return None
        self._warned_get_failure_endpoints.discard(endpoint)
        if not isinstance(payload, dict):
            log_warning(
                _LOGGER,
                "Substitute BackEnd GET returned non-object JSON",
                endpoint=endpoint,
            )
            return None
        return payload

    def _post_json(self, path: str, body: JsonObject) -> JsonObject | None:
        """POST one backend route and return a JSON object on success."""

        try:
            response = self._http_post(
                self._url(path),
                json=body,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not _is_expected_http_error(error):
                raise
            log_warning(
                _LOGGER,
                "Substitute BackEnd POST failed",
                endpoint=self._url(path),
                error=repr(error),
            )
            return None
        if not isinstance(payload, dict):
            log_warning(
                _LOGGER,
                "Substitute BackEnd POST returned non-object JSON",
                endpoint=self._url(path),
            )
            return None
        return payload

    def _url(self, path: str) -> str:
        """Return an HTTP URL rooted at the configured Comfy endpoint."""

        return f"http://{self._endpoint.host}:{self._endpoint.port}{path}"


def _is_expected_http_error(error: BaseException) -> bool:
    """Return whether an HTTP operation failure should be converted to `None`."""

    return isinstance(error, TypeError | ValueError) or is_request_exception(error)


def _parse_model_catalog_entry(data: JsonObject) -> BackendModelCatalogEntry:
    """Parse one backend catalog entry into a typed DTO."""

    source = _read_object(data, "source")
    file_data = _read_object(data, "file")
    fingerprint = _read_object(data, "fingerprint")
    sidecar = _read_object(data, "sidecar")
    local_preview = _read_object(data, "localPreview")
    return BackendModelCatalogEntry(
        schema_version=_required_int(data, "schemaVersion"),
        target_id=_required_str(data, "targetId"),
        kind=_required_str(data, "kind"),
        value=_required_str(data, "value"),
        display_name=_required_str(data, "displayName"),
        source=BackendModelSource(
            root_id=_required_str(source, "rootId"),
            relative_path=_required_str(source, "relativePath"),
        ),
        file=BackendModelFile(
            extension=_required_str(file_data, "extension"),
            size_bytes=_required_int(file_data, "sizeBytes"),
            modified_at=_required_str(file_data, "modifiedAt"),
            created_at=_read_str(file_data, "createdAt"),
        ),
        fingerprint=BackendFingerprint(
            status=_parse_fingerprint_status(_required_str(fingerprint, "status")),
            sha256=_read_str(fingerprint, "sha256"),
            source=_read_str(fingerprint, "source"),
            computed_at=_read_str(fingerprint, "computedAt"),
            error=_read_str(fingerprint, "error"),
        ),
        sidecar=BackendSidecar(
            found=_read_bool(sidecar, "found"),
            model_id=_read_int(sidecar, "modelId"),
            model_version_id=_read_int(sidecar, "modelVersionId"),
            sha256=_read_str(sidecar, "sha256"),
            activation_text=_read_str(sidecar, "activationText"),
            description=_read_str(sidecar, "description"),
            base_model=_read_str(sidecar, "baseModel"),
            modified_at=_read_str(sidecar, "modifiedAt"),
        ),
        local_preview=BackendLocalPreview(
            available=_read_bool(local_preview, "available"),
            preview_id=_read_str(local_preview, "previewId"),
            url=_read_str(local_preview, "url"),
            source=_read_str(local_preview, "source"),
            modified_at=_read_str(local_preview, "modifiedAt"),
            width=_read_int(local_preview, "width"),
            height=_read_int(local_preview, "height"),
        ),
    )


def _parse_fingerprint_job(data: JsonObject) -> BackendFingerprintJob:
    """Parse one backend fingerprint job payload."""

    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("entries must be a list")
    entries: list[BackendFingerprintJobEntry] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            continue
        entries.append(
            BackendFingerprintJobEntry(
                kind=_required_str(raw_entry, "kind"),
                value=_required_str(raw_entry, "value"),
                status=_parse_job_status(_required_str(raw_entry, "status")),
                sha256=_read_str(raw_entry, "sha256"),
                error=_read_str(raw_entry, "error"),
            )
        )
    return BackendFingerprintJob(
        job_id=_required_str(data, "jobId"),
        status=_parse_job_status(_required_str(data, "status")),
        entries=tuple(entries),
    )


def _parse_hash_lookup_result(data: JsonObject) -> BackendHashLookupResult:
    """Parse one backend hash lookup response."""

    raw_matches = data.get("matches")
    if not isinstance(raw_matches, list):
        raise ValueError("matches must be a list")
    matches: list[BackendHashLookupMatch] = []
    for raw_match in raw_matches:
        if not isinstance(raw_match, dict):
            continue
        source = _read_object(raw_match, "source")
        file_data = _read_object(raw_match, "file")
        matches.append(
            BackendHashLookupMatch(
                kind=_required_str(raw_match, "kind"),
                value=_required_str(raw_match, "value"),
                display_name=_required_str(raw_match, "displayName"),
                source=BackendModelSource(
                    root_id=_required_str(source, "rootId"),
                    relative_path=_required_str(source, "relativePath"),
                ),
                file=BackendModelFile(
                    extension=_required_str(file_data, "extension"),
                    size_bytes=_required_int(file_data, "sizeBytes"),
                    modified_at=_required_str(file_data, "modifiedAt"),
                    created_at=_read_str(file_data, "createdAt"),
                ),
            )
        )
    return BackendHashLookupResult(
        status=_parse_hash_lookup_status(_required_str(data, "status")),
        kind=_required_str(data, "kind"),
        sha256=_required_str(data, "sha256").upper(),
        matches=tuple(matches),
        job_id=_read_str(data, "jobId"),
    )


def _parse_model_download_job(data: JsonObject) -> BackendModelDownloadJob:
    """Parse one backend model download job response."""

    result_payload = data.get("result")
    result = (
        _parse_model_download_result(result_payload)
        if isinstance(result_payload, dict)
        else None
    )
    return BackendModelDownloadJob(
        job_id=_required_str(data, "jobId"),
        status=_parse_model_download_status(_required_str(data, "status")),
        kind=_required_str(data, "kind"),
        sha256=_required_str(data, "sha256").upper(),
        value=_read_str(data, "value"),
        result=result,
        error=_read_str(data, "error"),
        bytes_downloaded=_read_int(data, "bytesDownloaded"),
        bytes_total=_read_int(data, "bytesTotal"),
        detail=_read_str(data, "detail"),
    )


def _parse_model_download_result(data: JsonObject) -> BackendModelDownloadResult:
    """Parse one verified backend model download result."""

    source = _read_object(data, "source")
    file_data = _read_object(data, "file")
    return BackendModelDownloadResult(
        kind=_required_str(data, "kind"),
        value=_required_str(data, "value"),
        display_name=_required_str(data, "displayName"),
        source=BackendModelSource(
            root_id=_required_str(source, "rootId"),
            relative_path=_required_str(source, "relativePath"),
        ),
        sha256=_required_str(data, "sha256").upper(),
        file=BackendModelFile(
            extension=_required_str(file_data, "extension"),
            size_bytes=_required_int(file_data, "sizeBytes"),
            modified_at=_required_str(file_data, "modifiedAt"),
            created_at=_read_str(file_data, "createdAt"),
        ),
    )


def _parse_fingerprint_status(value: str) -> FingerprintStatus:
    """Parse a backend fingerprint status with a safe fallback."""

    try:
        return FingerprintStatus(value)
    except ValueError:
        return FingerprintStatus.FAILED


def _parse_hash_lookup_status(value: str) -> BackendHashLookupStatus:
    """Parse a backend hash lookup status with a safe fallback."""

    try:
        return BackendHashLookupStatus(value)
    except ValueError:
        return BackendHashLookupStatus.UNAVAILABLE


def _parse_job_status(value: str) -> JobStatus:
    """Parse a backend job status with a safe fallback."""

    try:
        return JobStatus(value)
    except ValueError:
        return JobStatus.FAILED


def _parse_model_download_status(value: str) -> ModelDownloadStatus:
    """Parse a backend model download status with a safe fallback."""

    try:
        return ModelDownloadStatus(value)
    except ValueError:
        return ModelDownloadStatus.FAILED


def _read_object(data: JsonObject, key: str) -> JsonObject:
    """Read a required JSON object field."""

    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _parse_cube_library_capabilities(
    value: object,
) -> BackendCubeLibraryCapabilities:
    """Parse optional Cube Library capability facts from top-level capabilities."""

    if not isinstance(value, dict):
        return BackendCubeLibraryCapabilities()
    return BackendCubeLibraryCapabilities(
        schema_version=_read_int(value, "schemaVersion") or 0,
        available=_read_bool(value, "available"),
        unavailable_reason=_read_str(value, "unavailableReason") or "",
        sugar_cubes_version=_read_str(value, "sugarCubesVersion") or "",
        catalog_supported=_read_bool(value, "catalogSupported"),
        artifact_load_supported=_read_bool(value, "artifactLoadSupported"),
        workflow_compile_supported=_read_bool(value, "workflowCompileSupported"),
        pack_management_supported=_read_bool(value, "packManagementSupported"),
        dependency_readiness_supported=_read_bool(
            value, "dependencyReadinessSupported"
        ),
        dependency_repair_supported=_read_bool(value, "dependencyRepairSupported"),
        versioned_dependency_readiness_supported=_read_bool(
            value, "versionedDependencyReadinessSupported"
        ),
        sync_dependency_orchestration_supported=_read_bool(
            value, "syncDependencyOrchestrationSupported"
        ),
    )


def _parse_sugar_compile_capabilities(
    value: object,
) -> BackendSugarCompileCapabilities:
    """Parse optional Sugar compile capability facts from top-level capabilities."""

    if not isinstance(value, dict):
        return BackendSugarCompileCapabilities()
    return BackendSugarCompileCapabilities(
        schema_version=_read_int(value, "schemaVersion") or 0,
        available=_read_bool(value, "available"),
        unavailable_reason=_read_str(value, "unavailableReason") or "",
        compile_route=_read_str(value, "compileRoute") or "",
        sugar_dsl_version=_read_str(value, "sugarDslVersion") or "",
    )


def _required_str(data: JsonObject, key: str) -> str:
    """Read a required string field."""

    value = _read_str(data, key)
    if value is None:
        raise ValueError(f"{key} must be a string")
    return value


def _read_str(data: JsonObject, key: str) -> str | None:
    """Read an optional string field."""

    value = data.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _required_int(data: JsonObject, key: str) -> int:
    """Read a required integer field."""

    value = _read_int(data, key)
    if value is None:
        raise ValueError(f"{key} must be an integer")
    return value


def _read_int(data: JsonObject, key: str) -> int | None:
    """Read an optional integer field."""

    value = data.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _read_bool(data: JsonObject, key: str) -> bool:
    """Read an optional boolean field with a false default."""

    value = data.get(key)
    return value if isinstance(value, bool) else False


def _read_str_tuple(data: JsonObject, key: str) -> tuple[str, ...]:
    """Read an optional list of strings as a tuple."""

    value = data.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())


__all__ = ["SubstituteBackendModelMetadataClient"]
