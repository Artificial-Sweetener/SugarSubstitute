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

"""Tests for Cube Library settings projection models."""

from __future__ import annotations

from substitute.application.cube_library import CubeLibrarySnapshot
from substitute.domain.cube_library import (
    CubeDependencyVersionPlanItem,
    CubeLibraryReadiness,
    CubeLibraryStatus,
    CubePackRecord,
    CubeRuntimeReadiness,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.application.cube_library.settings_projection import (
    BASE_PACK_REMOVE_DISABLED_REASON,
    project_library_status,
    project_pack,
    project_readiness,
)


def test_project_pack_builds_summary_badges_and_detail_rows() -> None:
    """Pack projection should expose collapsed summary and expanded details."""

    view = project_pack(
        _pack(
            enabled=False,
            default_base_repo=True,
            update_available=True,
            last_sync_status="failed",
            last_sync_error="network unavailable",
            last_check_status="clean",
        )
    )

    assert view.title == "Owner/Repo"
    assert view.subtitle == "2 cubes · Sync failed · Disabled · Update available"
    assert [(badge.text, badge.severity) for badge in view.badges] == [
        ("Base", "neutral"),
        ("Disabled", "warning"),
        ("Update available", "warning"),
        ("Sync failed", "error"),
    ]
    assert view.enabled is False
    assert view.can_remove is False
    assert view.remove_disabled_reason == BASE_PACK_REMOVE_DISABLED_REASON
    assert ("Last sync error", "network unavailable", "error") in [
        (detail.label, detail.value, detail.severity) for detail in view.details
    ]
    detail_labels = [detail.label for detail in view.details]
    assert "Local revision" not in detail_labels
    assert "Remote revision" not in detail_labels
    assert "Last check status" not in detail_labels


def test_project_pack_hides_empty_error_rows_and_uses_placeholders() -> None:
    """Projection should not render blank errors or blank status values."""

    view = project_pack(
        _pack(
            branch="",
            last_sync_status="",
            last_sync_at="",
            last_check_status="",
            local_head_sha="",
            remote_head_sha="",
        )
    )

    assert view.subtitle == "2 cubes · Never synced"
    labels = {detail.label: detail.value for detail in view.details}
    assert labels["Cubes"] == "2 cubes"
    assert labels["Last synced"] == "Never"
    assert "Last sync error" not in labels
    assert "Last check error" not in labels


def test_project_pack_lists_cube_paths_when_available() -> None:
    """Projection should show cube paths when the snapshot provides them."""

    view = project_pack(_pack(), cube_paths=("demo.cube", "nested/upscale.cube"))

    labels = {detail.label: detail.value for detail in view.details}

    assert labels["Cubes"] == "demo.cube, nested/upscale.cube"


def test_project_readiness_lists_missing_nodes() -> None:
    """Missing readiness projection should include the node names."""

    view = project_readiness(
        _readiness(
            ready=False,
            required_custom_nodes=("Impact", "Manager"),
            missing_custom_nodes=("Impact",),
            installed_custom_nodes=("Manager",),
            errors=("Cannot install automatically.",),
        )
    )

    assert view.ready is False
    assert view.summary == "Missing custom nodes: 1"
    assert [
        (detail.label, detail.value, detail.severity) for detail in view.details
    ] == [
        ("Required custom nodes", "Impact, Manager", "neutral"),
        ("Missing custom nodes", "Impact", "error"),
        ("Installed custom nodes", "Manager", "neutral"),
        ("Install support", "No", "neutral"),
        ("Can install", "No", "neutral"),
        ("Readiness errors", "Cannot install automatically.", "error"),
    ]


def test_project_readiness_handles_ready_and_unavailable_states() -> None:
    """Readiness projection should distinguish ready and unavailable states."""

    ready = project_readiness(
        _readiness(
            ready=True,
            required_custom_nodes=("Impact",),
            missing_custom_nodes=(),
            installed_custom_nodes=("Impact",),
        )
    )
    unavailable = project_readiness(None)

    assert ready.ready is True
    assert ready.summary == "Required custom nodes are installed."
    assert unavailable.ready is False
    assert unavailable.summary == "Readiness unavailable from the active target."


def test_project_readiness_lists_version_and_runtime_issues() -> None:
    """Version readiness should affect the target readiness projection."""

    view = project_readiness(
        _readiness(
            ready=True,
            required_custom_nodes=("SimpleSyrup",),
            missing_custom_nodes=(),
            installed_custom_nodes=("SimpleSyrup",),
            dependency_version_plan=(
                CubeDependencyVersionPlanItem(
                    node_id="SimpleSyrup",
                    display_name="SimpleSyrup",
                    required_version="f561",
                    required_version_kind="git_sha",
                    installed_version="37bc",
                    installed_version_kind="git_sha",
                    status="installed_commit_not_descendant",
                    repairable=True,
                    restart_required_after_repair=True,
                    required_by_packs=("Artificial-Sweetener/Base-Cubes",),
                    required_by_cube_ids=("demo.cube",),
                    required_by_nodes=("Detailer",),
                    remediation="Update SimpleSyrup.",
                ),
            ),
            comfy_runtime=CubeRuntimeReadiness(
                schema_version=1,
                required_version="0.3.66",
                required_version_kind="semver",
                installed_version="",
                status="installed_version_unknown",
            ),
        )
    )

    assert view.ready is False
    assert view.summary == "Dependency version issues: 2"
    assert (
        "Dependency versions",
        "SimpleSyrup: installed_commit_not_descendant",
        "error",
    ) in [(detail.label, detail.value, detail.severity) for detail in view.details]
    assert ("Comfy runtime", "Comfy 0.3.66: installed_version_unknown", "error") in [
        (detail.label, detail.value, detail.severity) for detail in view.details
    ]


def test_project_library_status_reports_target_and_sync_all_availability() -> None:
    """Status projection should summarize target availability and sync-all state."""

    available = project_library_status(
        CubeLibrarySnapshot(
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            status=CubeLibraryStatus(
                schema_version=1,
                available=True,
                source="test",
                catalog_revision="sha256:test",
                pack_management_supported=True,
                local_authoring_supported=False,
                readiness_supported=True,
                errors=(),
            ),
            packs=(_pack(enabled=True),),
            readiness=None,
            cube_paths_by_pack={},
        )
    )
    unavailable = project_library_status(None)

    assert available.available is True
    assert available.description == "Connected to 127.0.0.1:8188."
    assert available.can_sync_all is True
    assert unavailable.available is False
    assert unavailable.can_sync_all is False


def _pack(
    *,
    repo_ref: str = "Owner/Repo",
    owner: str = "Owner",
    repo: str = "Repo",
    branch: str = "main",
    enabled: bool = True,
    default_base_repo: bool = False,
    auto_update: bool = False,
    local_head_sha: str = "abcdef1234567890",
    remote_head_sha: str = "fedcba0987654321",
    update_available: bool = False,
    last_sync_at: str = "2026-05-03T00:00:00Z",
    last_sync_status: str = "clean",
    last_sync_error: str = "",
    last_checked_at: str = "2026-05-03T00:00:00Z",
    last_check_status: str = "clean",
    last_check_error: str = "",
    cube_count: int = 2,
) -> CubePackRecord:
    """Build one Cube Pack record for projection tests."""

    return CubePackRecord(
        repo_ref=repo_ref,
        owner=owner,
        repo=repo,
        branch=branch,
        enabled=enabled,
        default_base_repo=default_base_repo,
        auto_update=auto_update,
        local_head_sha=local_head_sha,
        remote_head_sha=remote_head_sha,
        update_available=update_available,
        last_sync_at=last_sync_at,
        last_sync_status=last_sync_status,
        last_sync_error=last_sync_error,
        last_checked_at=last_checked_at,
        last_check_status=last_check_status,
        last_check_error=last_check_error,
        cube_count=cube_count,
    )


def _readiness(
    *,
    ready: bool,
    required_custom_nodes: tuple[str, ...],
    missing_custom_nodes: tuple[str, ...],
    installed_custom_nodes: tuple[str, ...],
    errors: tuple[str, ...] = (),
    dependency_version_plan: tuple[CubeDependencyVersionPlanItem, ...] = (),
    comfy_runtime: CubeRuntimeReadiness | None = None,
) -> CubeLibraryReadiness:
    """Build readiness data for projection tests."""

    return CubeLibraryReadiness(
        schema_version=1,
        ready=ready,
        required_custom_nodes=required_custom_nodes,
        missing_custom_nodes=missing_custom_nodes,
        installed_custom_nodes=installed_custom_nodes,
        can_install=False,
        install_supported=False,
        catalog_revision="sha256:test",
        errors=errors,
        dependency_version_plan=dependency_version_plan,
        comfy_runtime=comfy_runtime,
    )
