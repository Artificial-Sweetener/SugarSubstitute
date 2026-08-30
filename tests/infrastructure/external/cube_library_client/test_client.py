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

"""Verify version-first Cube Library HTTP client contracts."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.cube_library import (
    CubeDependencyRepairRequest,
    CubeDependencySyncAndCheckRequest,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.substitute_backend_cube_library_client import (
    SubstituteBackendCubeLibraryClient,
)


@dataclass(frozen=True)
class _Response:
    """Provide a minimal successful HTTP response double."""

    payload: object

    def raise_for_status(self) -> None:
        """Accept the configured successful response."""

    def json(self) -> object:
        """Return the configured response payload."""

        return self.payload


def test_client_lists_cube_versions() -> None:
    """Request the version-listing route for a cube identity."""

    requested: list[str] = []

    def fake_get(url: str, **kwargs: object) -> _Response:
        """Capture the request URL and return available versions."""

        _ = kwargs
        requested.append(url)
        return _Response({"schemaVersion": 1, "versions": ["2.0", "1.0"]})

    client = SubstituteBackendCubeLibraryClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_get=fake_get,
    )

    versions = client.list_cube_versions("Owner/Repo/demo.cube")

    assert versions == ("2.0", "1.0")
    assert requested == [
        "http://127.0.0.1:8188/substitute/v1/cube-library/cubes/versions?"
        "cubeId=Owner%2FRepo%2Fdemo.cube"
    ]


def test_client_loads_cube_by_version() -> None:
    """Request an artifact using only its cube identity and version."""

    requested: list[str] = []

    def fake_get(url: str, **kwargs: object) -> _Response:
        """Capture the request URL and return one artifact."""

        _ = kwargs
        requested.append(url)
        return _Response(_artifact_payload(version="2.0"))

    client = SubstituteBackendCubeLibraryClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_get=fake_get,
    )

    artifact = client.load_cube_version("Owner/Repo/demo.cube", "2.0")

    assert artifact is not None
    assert artifact.cube_id == "Owner/Repo/demo.cube"
    assert artifact.version == "2.0"
    assert requested == [
        "http://127.0.0.1:8188/substitute/v1/cube-library/cubes/load?"
        "cubeId=Owner%2FRepo%2Fdemo.cube&version=2.0"
    ]


def test_client_parses_dependency_readiness_install_plan() -> None:
    """Preserve dependency install-plan details from the backend response."""

    client = SubstituteBackendCubeLibraryClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_get=lambda _url, **_kwargs: _Response(_readiness_payload()),
    )

    readiness = client.get_dependency_readiness()

    assert readiness is not None
    assert readiness.install_supported is True
    assert readiness.restart_required is True
    assert readiness.install_plan[0].node_id == "comfyui-example"
    assert readiness.install_plan[0].required_by_packs == ("Example/Cubes",)
    assert readiness.install_plan[0].confirmation_required is True
    assert readiness.versioned_requirements_supported is True
    assert readiness.dependency_version_plan[0].status == "installed_version_unknown"
    assert readiness.comfy_runtime is not None
    assert readiness.comfy_runtime.required_version == "0.3.66"


def test_client_posts_dependency_repair_request() -> None:
    """Post dependency repairs through the dedicated backend route."""

    posted: list[tuple[str, dict[str, object]]] = []

    def fake_post(url: str, *, json: dict[str, object], **kwargs: object) -> _Response:
        """Capture the request and return a completed repair result."""

        _ = kwargs
        posted.append((url, json))
        return _Response(
            {
                "schemaVersion": 1,
                "readinessBefore": _readiness_payload(),
                "attemptedInstallPlan": _readiness_payload()["installPlan"],
                "installedNodes": [{"nodeId": "comfyui-example"}],
                "skippedNodes": [],
                "failedNodes": [],
                "readinessAfter": {**_readiness_payload(), "ready": True},
                "restartRequired": True,
            }
        )

    client = SubstituteBackendCubeLibraryClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_post=fake_post,
    )

    result = client.repair_dependencies(
        CubeDependencyRepairRequest(
            approved_node_ids=("comfyui-example",),
            sync_enabled_repos=True,
        )
    )

    assert result is not None
    assert result.installed_nodes == ("comfyui-example",)
    assert result.restart_required is True
    assert posted == [
        (
            "http://127.0.0.1:8188/substitute/v1/cube-library/dependencies/repair",
            {
                "baselineOnly": False,
                "approvedNodeIds": ["comfyui-example"],
                "syncEnabledRepos": True,
            },
        )
    ]


def test_client_posts_sync_and_check_request() -> None:
    """Post sync-and-check orchestration to the shared backend route."""

    posted: list[tuple[str, dict[str, object]]] = []

    def fake_post(url: str, *, json: dict[str, object], **kwargs: object) -> _Response:
        """Capture the request and return a completed orchestration result."""

        _ = kwargs
        posted.append((url, json))
        return _Response(
            {
                "schemaVersion": 1,
                "syncedPacks": [],
                "dependencyReadiness": _readiness_payload(),
                "repairPlan": {},
                "repairResult": None,
                "restartRequired": True,
                "errors": [],
            }
        )

    client = SubstituteBackendCubeLibraryClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_post=fake_post,
    )

    result = client.sync_and_check(CubeDependencySyncAndCheckRequest(sync_mode="all"))

    assert result is not None
    assert result.restart_required is True
    assert posted == [
        (
            "http://127.0.0.1:8188/substitute/v1/cube-library/sync-and-check",
            {
                "sync": {"mode": "all", "owner": "", "repo": ""},
                "dependencyPolicy": {
                    "includeVersions": True,
                    "baselineOnly": False,
                    "approvedNodeIds": [],
                    "repair": False,
                },
            },
        )
    ]


def _artifact_payload(*, version: str) -> dict[str, object]:
    """Build a backend artifact payload."""

    return {
        "schemaVersion": 1,
        "cubeId": "Owner/Repo/demo.cube",
        "version": version,
        "displayName": "Demo",
        "contentHash": "sha256:diagnostic",
        "source": {"kind": "local", "path": "demo.cube"},
        "cube": {"cube_id": "Owner/Repo/demo.cube", "version": version, "nodes": {}},
    }


def _readiness_payload() -> dict[str, object]:
    """Build a dependency readiness payload with one missing node."""

    return {
        "schemaVersion": 1,
        "ready": False,
        "requiredCustomNodes": ["comfyui-example"],
        "missingCustomNodes": ["comfyui-example"],
        "installedCustomNodes": [],
        "canInstall": True,
        "installSupported": True,
        "catalogRevision": "sha256:catalog",
        "errors": [],
        "restartRequired": True,
        "versionedRequirementsSupported": True,
        "dependencyVersionPlan": [
            {
                "nodeId": "comfyui-example",
                "displayName": "Example Nodes",
                "requiredVersion": "1.2.0",
                "requiredVersionKind": "semver",
                "installedVersion": "",
                "installedVersionKind": "missing",
                "status": "installed_version_unknown",
                "repairable": False,
                "restartRequiredAfterRepair": False,
                "requiredByPacks": ["Example/Cubes"],
                "requiredByCubeIds": ["Example/Cubes/demo.cube"],
                "requiredByNodes": ["Example Node"],
                "remediation": "Installed custom-node version could not be proven safely.",
            }
        ],
        "comfyRuntimeReadiness": {
            "schemaVersion": 1,
            "requiredVersion": "0.3.66",
            "requiredVersionKind": "semver",
            "installedVersion": "",
            "status": "installed_version_unknown",
            "remediation": "Comfy runtime version could not be read.",
        },
        "installPlan": [
            {
                "nodeId": "comfyui-example",
                "displayName": "Example Nodes",
                "existingFolderName": "",
                "requiredByPacks": ["Example/Cubes"],
                "requiredByCubeIds": ["Example/Cubes/demo.cube"],
                "defaultBaseOnly": False,
                "confirmationRequired": True,
                "installable": True,
                "installed": False,
                "remediation": "",
            }
        ],
    }
