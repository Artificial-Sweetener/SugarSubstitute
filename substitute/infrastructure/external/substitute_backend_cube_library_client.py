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

"""HTTP client for Substitute BackEnd Cube Library routes."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any
from urllib.parse import quote

from substitute.domain.common import JsonObject
from substitute.domain.cube_library import (
    CubeCatalog,
    CubeCatalogEntry,
    CubeDependencyInstallPlanItem,
    CubeDependencyRepairRequest,
    CubeDependencyRepairResult,
    CubeDependencySyncAndCheckRequest,
    CubeDependencySyncAndCheckResult,
    CubeDependencyVersionPlanItem,
    CubeIconDescriptor,
    CubeLibraryReadiness,
    CubeLibraryStatus,
    CubePackPreflight,
    CubePackRecord,
    CubeRuntimeReadiness,
    CubeSourceMetadata,
    LoadedCubeArtifact,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import (
    default_http_delete,
    default_http_get,
    default_http_post,
    is_request_exception,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_timing,
    log_warning,
)
from substitute.shared.startup_trace import trace_mark, trace_span

_LOGGER = get_logger("infrastructure.external.substitute_backend_cube_library_client")
HttpGet = Callable[..., Any]
HttpPost = Callable[..., Any]
HttpDelete = Callable[..., Any]
_SUPPORTED_ICON_MEDIA_TYPES = {"", "image/png", "image/svg+xml"}
_ICON_COLOR_BEHAVIORS = {"auto", "template", "fullColor", "themeVariants"}


class SubstituteBackendCubeLibraryClient:
    """Query Cube Library routes exposed by the active Substitute BackEnd target."""

    def __init__(
        self,
        endpoint: ComfyEndpoint,
        *,
        http_get: HttpGet | None = None,
        http_post: HttpPost | None = None,
        http_delete: HttpDelete | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        """Initialize the client with endpoint and injectable HTTP transport."""

        self._endpoint = endpoint
        self._http_get = http_get or default_http_get
        self._http_post = http_post or default_http_post
        self._http_delete = http_delete or default_http_delete
        self._timeout_seconds = timeout_seconds

    def get_status(self) -> CubeLibraryStatus | None:
        """Return target Cube Library status or ``None`` when unavailable."""

        payload = self._get_json("/substitute/v1/cube-library/status")
        if payload is None:
            return None
        try:
            return _parse_status(payload)
        except ValueError as error:
            log_warning(
                _LOGGER, "Invalid Cube Library status payload", error=repr(error)
            )
            return None

    def get_catalog(self) -> CubeCatalog | None:
        """Return target Cube Library catalog or ``None`` when unavailable."""

        payload = self._get_json("/substitute/v1/cube-library/catalog")
        if payload is None:
            return None
        try:
            return _parse_catalog(payload)
        except ValueError as error:
            log_warning(
                _LOGGER, "Invalid Cube Library catalog payload", error=repr(error)
            )
            return None

    def load_cube(self, cube_id: str) -> LoadedCubeArtifact | None:
        """Return one loaded cube artifact or ``None`` when unavailable."""

        payload = self.load_cube_payload(cube_id)
        if payload is None:
            return None
        try:
            return _parse_loaded_artifact(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Cube Library artifact payload",
                cube_id=cube_id,
                error=repr(error),
            )
            return None

    def load_cube_payload(self, cube_id: str) -> JsonObject | None:
        """Return one raw loaded cube artifact payload for local compilation."""

        encoded_cube_id = quote(cube_id, safe="")
        payload = self._get_json(
            f"/substitute/v1/cube-library/cubes/load?cubeId={encoded_cube_id}"
        )
        if payload is None:
            return None
        try:
            _parse_loaded_artifact(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Cube Library artifact payload",
                cube_id=cube_id,
                error=repr(error),
            )
            return None
        return payload

    def load_cube_version(
        self,
        cube_id: str,
        version: str,
    ) -> LoadedCubeArtifact | None:
        """Return one loaded cube artifact by selected version."""

        payload = self.load_cube_version_payload(cube_id, version)
        if payload is None:
            return None
        try:
            return _parse_loaded_artifact(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid versioned Cube Library artifact payload",
                cube_id=cube_id,
                cube_version=version,
                error=repr(error),
            )
            return None

    def load_cube_version_payload(
        self,
        cube_id: str,
        version: str,
    ) -> JsonObject | None:
        """Return one raw versioned artifact payload for local compilation."""

        encoded_cube_id = quote(cube_id, safe="")
        encoded_version = quote(version, safe="")
        payload = self._get_json(
            "/substitute/v1/cube-library/cubes/load?"
            f"cubeId={encoded_cube_id}&version={encoded_version}"
        )
        if payload is None:
            return None
        try:
            _parse_loaded_artifact(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid versioned Cube Library artifact payload",
                cube_id=cube_id,
                cube_version=version,
                error=repr(error),
            )
            return None
        return payload

    def prewarm_cube_version(self, cube_id: str, version: str) -> bool:
        """Schedule best-effort warming for one cube version artifact."""

        payload = self._post_json(
            "/substitute/v1/cube-library/cubes/prewarm",
            {"cubeId": cube_id, "version": version},
        )
        return bool(payload and payload.get("accepted") is True)

    def list_cube_versions(self, cube_id: str) -> tuple[str, ...]:
        """Return versions available for one Cube Library cube id."""

        encoded_cube_id = quote(cube_id, safe="")
        payload = self._get_json(
            f"/substitute/v1/cube-library/cubes/versions?cubeId={encoded_cube_id}"
        )
        if payload is None:
            return ()
        try:
            return _parse_cube_versions(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Cube Library versions payload",
                cube_id=cube_id,
                error=repr(error),
            )
            return ()

    def list_packs(self) -> tuple[CubePackRecord, ...]:
        """Return tracked Cube Packs reported by the active target."""

        payload = self._get_json("/substitute/v1/cube-library/packs")
        if payload is None:
            return ()
        raw_packs = payload.get("packs")
        if not isinstance(raw_packs, list):
            log_warning(_LOGGER, "Invalid Cube Library packs payload")
            return ()
        packs: list[CubePackRecord] = []
        for raw_pack in raw_packs:
            if not isinstance(raw_pack, dict):
                continue
            try:
                packs.append(_parse_pack(raw_pack))
            except ValueError as error:
                log_warning(
                    _LOGGER,
                    "Skipped invalid Cube Library pack payload",
                    error=repr(error),
                )
        return tuple(packs)

    def preflight_pack(
        self,
        *,
        owner: str,
        repo: str,
        branch: str,
    ) -> CubePackPreflight | None:
        """Return candidate Cube Pack preflight results."""

        payload = self._post_json(
            "/substitute/v1/cube-library/packs/preflight",
            {"owner": owner, "repo": repo, "branch": branch},
        )
        if payload is None:
            return None
        try:
            return _parse_preflight(_read_object(payload, "preflight"))
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Cube Library preflight payload",
                error=repr(error),
            )
            return None

    def add_pack(
        self,
        *,
        owner: str,
        repo: str,
        branch: str,
        enabled: bool,
        auto_update: bool,
        sync_immediately: bool,
    ) -> CubePackRecord | None:
        """Track one Cube Pack on the active target."""

        payload = self._post_json(
            "/substitute/v1/cube-library/packs",
            {
                "owner": owner,
                "repo": repo,
                "branch": branch,
                "enabled": enabled,
                "autoUpdate": auto_update,
                "syncImmediately": sync_immediately,
            },
        )
        return _parse_optional_pack_response(payload, "add pack")

    def update_pack(
        self,
        *,
        owner: str,
        repo: str,
        branch: str | None,
        enabled: bool | None,
        auto_update: bool | None,
    ) -> CubePackRecord | None:
        """Update one tracked Cube Pack on the active target."""

        body: JsonObject = {"owner": owner, "repo": repo}
        if branch is not None:
            body["branch"] = branch
        if enabled is not None:
            body["enabled"] = enabled
        if auto_update is not None:
            body["autoUpdate"] = auto_update
        payload = self._post_json("/substitute/v1/cube-library/packs/update", body)
        return _parse_optional_pack_response(payload, "update pack")

    def remove_pack(self, *, owner: str, repo: str) -> bool:
        """Remove one tracked Cube Pack from the active target."""

        encoded_owner = quote(owner, safe="")
        encoded_repo = quote(repo, safe="")
        payload = self._delete_json(
            "/substitute/v1/cube-library/packs"
            f"?owner={encoded_owner}&repo={encoded_repo}"
        )
        return payload is not None

    def sync_pack(self, *, owner: str, repo: str) -> CubePackRecord | None:
        """Synchronously sync one tracked Cube Pack on the active target."""

        payload = self._post_json(
            "/substitute/v1/cube-library/packs/sync",
            {"owner": owner, "repo": repo},
        )
        return _parse_optional_pack_response(payload, "sync pack")

    def sync_all_packs(self) -> tuple[CubePackRecord, ...]:
        """Synchronously sync all enabled Cube Packs on the active target."""

        payload = self._post_json(
            "/substitute/v1/cube-library/packs/sync-all",
            {},
        )
        if payload is None:
            return ()
        raw_packs = payload.get("packs")
        if not isinstance(raw_packs, list):
            return ()
        packs: list[CubePackRecord] = []
        for raw_pack in raw_packs:
            if not isinstance(raw_pack, dict):
                continue
            try:
                packs.append(_parse_pack(raw_pack))
            except ValueError as error:
                log_warning(
                    _LOGGER,
                    "Skipped invalid Cube Library sync-all pack payload",
                    error=repr(error),
                )
        return tuple(packs)

    def get_readiness(self) -> CubeLibraryReadiness | None:
        """Return target dependency readiness or ``None`` when unavailable."""

        payload = self._get_json("/substitute/v1/cube-library/readiness")
        if payload is None:
            return None
        try:
            return _parse_readiness(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Cube Library readiness payload",
                error=repr(error),
            )
            return None

    def get_dependency_readiness(self) -> CubeLibraryReadiness | None:
        """Return install-capable dependency readiness when available."""

        payload = self._get_json("/substitute/v1/cube-library/dependencies/readiness")
        if payload is None:
            return None
        try:
            return _parse_readiness(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Cube Library dependency readiness payload",
                error=repr(error),
            )
            return None

    def repair_dependencies(
        self,
        request: CubeDependencyRepairRequest,
    ) -> CubeDependencyRepairResult | None:
        """Repair approved Cube Library dependencies on the active target."""

        payload = self._post_json(
            "/substitute/v1/cube-library/dependencies/repair",
            request.to_payload(),
        )
        if payload is None:
            return None
        try:
            return _parse_repair_result(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Cube Library dependency repair payload",
                error=repr(error),
            )
            return None

    def sync_and_check(
        self,
        request: CubeDependencySyncAndCheckRequest,
    ) -> CubeDependencySyncAndCheckResult | None:
        """Run shared Cube Pack sync and dependency readiness orchestration."""

        payload = self._post_json(
            "/substitute/v1/cube-library/sync-and-check",
            request.to_payload(),
        )
        if payload is None:
            return None
        try:
            return _parse_sync_and_check_result(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Cube Library sync-and-check payload",
                error=repr(error),
            )
            return None

    def _get_json(self, path: str) -> JsonObject | None:
        """GET one Cube Library route and return a JSON object on success."""

        url = self._url(path)
        started_at = perf_counter()
        trace_fields = {
            "path": path,
            "is_cube_load": path.startswith("/substitute/v1/cube-library/cubes/load"),
        }
        try:
            with trace_span("cube_library_http.get", **trace_fields):
                response = self._http_get(
                    url,
                    timeout=self._timeout_seconds,
                )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not _is_expected_http_error(error):
                raise
            trace_mark(
                "cube_library_http.get.failure",
                **trace_fields,
                error=repr(error),
            )
            log_timing(
                _LOGGER,
                "Cube Library GET failed after request timing",
                started_at=started_at,
                endpoint=url,
                error=repr(error),
            )
            log_warning(
                _LOGGER,
                "Substitute BackEnd Cube Library GET failed",
                endpoint=url,
                error=repr(error),
            )
            return None
        if not isinstance(payload, dict):
            trace_mark(
                "cube_library_http.get.invalid_json",
                **trace_fields,
                payload_type=type(payload).__name__,
            )
            log_timing(
                _LOGGER,
                "Cube Library GET returned invalid JSON object",
                started_at=started_at,
                endpoint=url,
                payload_type=type(payload).__name__,
            )
            log_warning(
                _LOGGER,
                "Substitute BackEnd Cube Library GET returned non-object JSON",
                endpoint=url,
            )
            return None
        content_length = getattr(response, "headers", {}).get("Content-Length", "")
        trace_mark(
            "cube_library_http.get.success",
            **trace_fields,
            status_code=getattr(response, "status_code", ""),
            content_length=content_length,
            top_level_key_count=len(payload),
        )
        log_timing(
            _LOGGER,
            "Cube Library GET returned JSON object",
            started_at=started_at,
            endpoint=url,
            top_level_key_count=len(payload),
            content_length=content_length,
        )
        return payload

    def _post_json(self, path: str, body: JsonObject) -> JsonObject | None:
        """POST one Cube Library route and return a JSON object on success."""

        url = self._url(path)
        try:
            response = self._http_post(
                url,
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
                "Substitute BackEnd Cube Library POST failed",
                endpoint=url,
                error=repr(error),
            )
            return None
        if not isinstance(payload, dict):
            log_warning(
                _LOGGER,
                "Substitute BackEnd Cube Library POST returned non-object JSON",
                endpoint=url,
            )
            return None
        return payload

    def _delete_json(self, path: str) -> JsonObject | None:
        """DELETE one Cube Library route and return a JSON object on success."""

        url = self._url(path)
        try:
            response = self._http_delete(url, timeout=self._timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not _is_expected_http_error(error):
                raise
            log_warning(
                _LOGGER,
                "Substitute BackEnd Cube Library DELETE failed",
                endpoint=url,
                error=repr(error),
            )
            return None
        if not isinstance(payload, dict):
            log_warning(
                _LOGGER,
                "Substitute BackEnd Cube Library DELETE returned non-object JSON",
                endpoint=url,
            )
            return None
        return payload

    def _url(self, path: str) -> str:
        """Return an HTTP URL rooted at the configured Comfy endpoint."""

        return f"http://{self._endpoint.host}:{self._endpoint.port}{path}"


def _is_expected_http_error(error: BaseException) -> bool:
    """Return whether an HTTP operation failure should be converted to `None`."""

    return isinstance(error, TypeError | ValueError) or is_request_exception(error)


def _parse_status(data: JsonObject) -> CubeLibraryStatus:
    """Parse Cube Library status payload."""

    return CubeLibraryStatus(
        schema_version=_required_int(data, "schemaVersion"),
        available=_read_bool(data, "available"),
        source=_required_str(data, "source"),
        catalog_revision=_read_str(data, "catalogRevision"),
        pack_management_supported=_read_bool(data, "packManagementSupported"),
        local_authoring_supported=_read_bool(data, "localAuthoringSupported"),
        readiness_supported=_read_bool(data, "readinessSupported"),
        errors=_read_error_messages(data.get("errors")),
    )


def _parse_catalog(data: JsonObject) -> CubeCatalog:
    """Parse Cube Library catalog payload."""

    raw_cubes = data.get("cubes")
    if not isinstance(raw_cubes, list):
        raise ValueError("cubes must be a list")
    return CubeCatalog(
        schema_version=_required_int(data, "schemaVersion"),
        catalog_revision=_required_str(data, "catalogRevision"),
        generated_at=_read_str(data, "generatedAt"),
        cubes=tuple(
            _parse_catalog_entry(raw_cube)
            for raw_cube in raw_cubes
            if isinstance(raw_cube, dict)
        ),
    )


def _parse_catalog_entry(data: JsonObject) -> CubeCatalogEntry:
    """Parse one Cube Library catalog entry."""

    return CubeCatalogEntry(
        cube_id=_required_str(data, "cubeId"),
        version=_read_str(data, "version"),
        display_name=_required_str(data, "displayName"),
        description=_read_str(data, "description"),
        source=_parse_source(_read_object(data, "source")),
        content_hash=_required_str(data, "contentHash"),
        updated_at=_read_str(data, "updatedAt"),
        supported_models=(
            _read_str_tuple(data, "supportedModels")
            or _read_str_tuple(data, "supported_models")
        ),
        icon=_parse_icon(data.get("icon")),
    )


def _parse_loaded_artifact(data: JsonObject) -> LoadedCubeArtifact:
    """Parse one loaded Cube Library artifact."""

    cube = _read_object(data, "cube")
    return LoadedCubeArtifact(
        cube_id=_required_str(data, "cubeId"),
        version=_read_str(data, "version"),
        display_name=_required_str(data, "displayName"),
        content_hash=_required_str(data, "contentHash"),
        source=_parse_source(_read_object(data, "source")),
        cube=cube,
        icon=_parse_icon(data.get("icon")),
    )


def _parse_cube_versions(data: JsonObject) -> tuple[str, ...]:
    """Parse available versions from the Cube Library versions route."""

    raw_versions = data.get("versions")
    if not isinstance(raw_versions, list):
        raise ValueError("versions must be a list")
    return tuple(
        version.strip()
        for version in raw_versions
        if isinstance(version, str) and version.strip()
    )


def _parse_icon(data: object) -> CubeIconDescriptor | None:
    """Parse optional Cube Library icon metadata without rejecting the cube."""

    if not isinstance(data, dict):
        return None
    kind = _read_str(data, "kind")
    media_type = (_read_str(data, "media_type") or _read_str(data, "mediaType")).lower()
    url = _read_str(data, "url")
    if (
        kind != "asset"
        or media_type not in _SUPPORTED_ICON_MEDIA_TYPES
        or not url.startswith("/")
        or url.startswith("//")
        or any(character.isspace() for character in url)
    ):
        return None
    return CubeIconDescriptor(
        kind=kind,
        url=url,
        media_type=media_type,
        repo_relative_path=(
            _read_str(data, "repo_relative_path") or _read_str(data, "repoRelativePath")
        ),
        color_behavior=_icon_color_behavior(data),
    )


def _parse_source(data: JsonObject) -> CubeSourceMetadata:
    """Parse Cube Library source metadata."""

    return CubeSourceMetadata(
        kind=_required_str(data, "kind"),
        repo_ref=_read_str(data, "repoRef"),
        owner=_read_str(data, "owner"),
        repo=_read_str(data, "repo"),
        branch=_read_str(data, "branch"),
        namespace=_read_str(data, "namespace"),
        path=_read_str(data, "path"),
        local_head_sha=_read_str(data, "localHeadSha"),
        remote_head_sha=_read_str(data, "remoteHeadSha"),
        dirty=_read_bool(data, "dirty"),
    )


def _parse_pack(data: JsonObject) -> CubePackRecord:
    """Parse one Cube Pack payload."""

    return CubePackRecord(
        repo_ref=_required_str(data, "repoRef"),
        owner=_required_str(data, "owner"),
        repo=_required_str(data, "repo"),
        branch=_required_str(data, "branch"),
        enabled=_read_bool(data, "enabled"),
        default_base_repo=_read_bool(data, "defaultBaseRepo"),
        auto_update=_read_bool(data, "autoUpdate"),
        local_head_sha=_read_str(data, "localHeadSha"),
        remote_head_sha=_read_str(data, "remoteHeadSha"),
        update_available=_read_bool(data, "updateAvailable"),
        last_sync_at=_read_str(data, "lastSyncAt"),
        last_sync_status=_read_str(data, "lastSyncStatus"),
        last_sync_error=_read_str(data, "lastSyncError"),
        last_checked_at=_read_str(data, "lastCheckedAt"),
        last_check_status=_read_str(data, "lastCheckStatus"),
        last_check_error=_read_str(data, "lastCheckError"),
        cube_count=_required_int(data, "cubeCount"),
    )


def _parse_preflight(data: JsonObject) -> CubePackPreflight:
    """Parse one Cube Pack preflight payload."""

    return CubePackPreflight(
        owner=_required_str(data, "owner"),
        repo=_required_str(data, "repo"),
        branch=_required_str(data, "branch"),
        contains_cubes=_read_bool(data, "containsCubes"),
        cube_count=_required_int(data, "cubeCount"),
        cube_paths=_read_str_tuple(data, "cubePaths"),
        truncated=_read_bool(data, "truncated"),
        checked_via=_read_str(data, "checkedVia"),
    )


def _parse_optional_pack_response(
    payload: JsonObject | None,
    operation: str,
) -> CubePackRecord | None:
    """Parse an optional pack mutation response with operation-specific logging."""

    if payload is None:
        return None
    try:
        return _parse_pack(_read_object(payload, "pack"))
    except ValueError as error:
        log_warning(
            _LOGGER,
            f"Invalid Cube Library {operation} payload",
            error=repr(error),
        )
        return None


def _parse_readiness(data: JsonObject) -> CubeLibraryReadiness:
    """Parse Cube Library readiness payload."""

    return CubeLibraryReadiness(
        schema_version=_required_int(data, "schemaVersion"),
        ready=_read_bool(data, "ready"),
        required_custom_nodes=_read_str_tuple(data, "requiredCustomNodes"),
        missing_custom_nodes=_read_str_tuple(data, "missingCustomNodes"),
        installed_custom_nodes=_read_str_tuple(data, "installedCustomNodes"),
        can_install=_read_bool(data, "canInstall"),
        install_supported=_read_bool(data, "installSupported"),
        catalog_revision=_read_str(data, "catalogRevision"),
        errors=_read_error_messages(data.get("errors")),
        install_plan=_parse_install_plan(data.get("installPlan")),
        restart_required=_read_bool(data, "restartRequired"),
        versioned_requirements_supported=_read_bool(
            data, "versionedRequirementsSupported"
        ),
        dependency_version_plan=_parse_dependency_version_plan(
            data.get("dependencyVersionPlan")
        ),
        comfy_runtime=_parse_comfy_runtime(data.get("comfyRuntimeReadiness")),
    )


def _parse_install_plan(value: object) -> tuple[CubeDependencyInstallPlanItem, ...]:
    """Parse dependency install plan items."""

    if not isinstance(value, list):
        return ()
    items: list[CubeDependencyInstallPlanItem] = []
    for raw_item in value:
        if not isinstance(raw_item, dict):
            continue
        items.append(
            CubeDependencyInstallPlanItem(
                node_id=_required_str(raw_item, "nodeId"),
                display_name=_read_str(raw_item, "displayName")
                or _required_str(raw_item, "nodeId"),
                existing_folder_name=_read_str(raw_item, "existingFolderName"),
                required_by_packs=_read_str_tuple(raw_item, "requiredByPacks"),
                required_by_cube_ids=_read_str_tuple(raw_item, "requiredByCubeIds"),
                default_base_only=_read_bool(raw_item, "defaultBaseOnly"),
                confirmation_required=_read_bool(raw_item, "confirmationRequired"),
                installable=_read_bool(raw_item, "installable"),
                installed=_read_bool(raw_item, "installed"),
                remediation=_read_str(raw_item, "remediation"),
            )
        )
    return tuple(items)


def _parse_repair_result(data: JsonObject) -> CubeDependencyRepairResult:
    """Parse dependency repair response payloads."""

    return CubeDependencyRepairResult(
        schema_version=_required_int(data, "schemaVersion"),
        readiness_before=_parse_readiness(_read_object(data, "readinessBefore")),
        attempted_install_plan=_parse_install_plan(data.get("attemptedInstallPlan")),
        installed_nodes=_parse_node_result_ids(data.get("installedNodes")),
        skipped_nodes=_parse_node_result_ids(data.get("skippedNodes")),
        failed_nodes=_parse_node_result_ids(data.get("failedNodes")),
        readiness_after=_parse_readiness(_read_object(data, "readinessAfter")),
        restart_required=_read_bool(data, "restartRequired"),
    )


def _parse_sync_and_check_result(data: JsonObject) -> CubeDependencySyncAndCheckResult:
    """Parse shared sync/check orchestration response payloads."""

    repair_payload = data.get("repairResult")
    return CubeDependencySyncAndCheckResult(
        schema_version=_required_int(data, "schemaVersion"),
        readiness=_parse_readiness(_read_object(data, "dependencyReadiness")),
        repair_result=(
            _parse_repair_result(repair_payload)
            if isinstance(repair_payload, dict)
            else None
        ),
        restart_required=_read_bool(data, "restartRequired"),
        errors=_read_error_messages(data.get("errors")),
    )


def _parse_dependency_version_plan(
    value: object,
) -> tuple[CubeDependencyVersionPlanItem, ...]:
    """Parse optional dependency version-plan items."""

    if not isinstance(value, list):
        return ()
    items: list[CubeDependencyVersionPlanItem] = []
    for raw_item in value:
        if not isinstance(raw_item, dict):
            continue
        items.append(
            CubeDependencyVersionPlanItem(
                node_id=_required_str(raw_item, "nodeId"),
                display_name=_read_str(raw_item, "displayName")
                or _required_str(raw_item, "nodeId"),
                required_version=_read_str(raw_item, "requiredVersion"),
                required_version_kind=_read_str(raw_item, "requiredVersionKind"),
                installed_version=_read_str(raw_item, "installedVersion"),
                installed_version_kind=_read_str(raw_item, "installedVersionKind"),
                status=_read_str(raw_item, "status"),
                repairable=_read_bool(raw_item, "repairable"),
                restart_required_after_repair=_read_bool(
                    raw_item, "restartRequiredAfterRepair"
                ),
                required_by_packs=_read_str_tuple(raw_item, "requiredByPacks"),
                required_by_cube_ids=_read_str_tuple(raw_item, "requiredByCubeIds"),
                required_by_nodes=_read_str_tuple(raw_item, "requiredByNodes"),
                remediation=_read_str(raw_item, "remediation"),
            )
        )
    return tuple(items)


def _parse_comfy_runtime(value: object) -> CubeRuntimeReadiness | None:
    """Parse optional Comfy runtime readiness facts."""

    if not isinstance(value, dict):
        return None
    return CubeRuntimeReadiness(
        schema_version=_required_int(value, "schemaVersion"),
        required_version=_read_str(value, "requiredVersion"),
        required_version_kind=_read_str(value, "requiredVersionKind"),
        installed_version=_read_str(value, "installedVersion"),
        status=_read_str(value, "status"),
        remediation=_read_str(value, "remediation"),
    )


def _parse_node_result_ids(value: object) -> tuple[str, ...]:
    """Return node ids from repair result item lists."""

    if not isinstance(value, list):
        return ()
    node_ids: list[str] = []
    for item in value:
        if isinstance(item, dict):
            node_id = _read_str(item, "nodeId")
            if node_id:
                node_ids.append(node_id)
    return tuple(node_ids)


def _read_object(data: JsonObject, key: str) -> JsonObject:
    """Read a required JSON object field."""

    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _required_str(data: JsonObject, key: str) -> str:
    """Read a required string field."""

    value = _read_str(data, key)
    if value:
        return value
    raise ValueError(f"{key} must be a string")


def _read_str(data: JsonObject, key: str) -> str:
    """Read an optional string field with an empty-string default."""

    value = data.get(key)
    return value.strip() if isinstance(value, str) else ""


def _required_int(data: JsonObject, key: str) -> int:
    """Read a required integer field."""

    value = data.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ValueError(f"{key} must be an integer")


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


def _read_error_messages(value: object) -> tuple[str, ...]:
    """Read backend error entries into displayable messages."""

    if not isinstance(value, list):
        return ()
    messages: list[str] = []
    for item in value:
        if isinstance(item, dict):
            message = item.get("message")
            if isinstance(message, str) and message.strip():
                messages.append(message.strip())
        elif isinstance(item, str) and item.strip():
            messages.append(item.strip())
    return tuple(messages)


def _icon_color_behavior(data: JsonObject) -> str:
    """Return the normalized icon color-behavior contract value."""

    raw_behavior = _read_str(data, "colorBehavior") or _read_str(data, "color_behavior")
    if raw_behavior in _ICON_COLOR_BEHAVIORS:
        return raw_behavior
    return "auto"


__all__ = ["SubstituteBackendCubeLibraryClient"]
