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

"""Coordinate active-target Cube Library management workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.application.ports import CubeLibraryClient
from substitute.domain.cube_library import (
    CubeDependencyInstallPlanItem,
    CubeDependencyRepairRequest,
    CubeDependencyRepairResult,
    CubeDependencySyncAndCheckRequest,
    CubeDependencySyncAndCheckResult,
    CubeLibraryReadiness,
    CubeLibraryStatus,
    CubePackPreflight,
    CubePackRecord,
)
from substitute.domain.onboarding import ComfyEndpoint


@dataclass(frozen=True)
class CubeLibrarySnapshot:
    """Represent current active-target Cube Library settings data."""

    endpoint: ComfyEndpoint
    status: CubeLibraryStatus | None
    packs: tuple[CubePackRecord, ...]
    readiness: CubeLibraryReadiness | None
    cube_paths_by_pack: Mapping[str, tuple[str, ...]]

    @property
    def available(self) -> bool:
        """Return whether the active target reports Cube Library support."""

        return self.status is not None and self.status.available


@dataclass(frozen=True)
class CubeDependencyRepairProposal:
    """Describe a UI-safe dependency repair operation."""

    baseline_only: bool
    approved_node_ids: tuple[str, ...]
    confirmation_node_labels: tuple[str, ...]

    @property
    def requires_confirmation(self) -> bool:
        """Return whether the user must approve the repair."""

        return bool(self.confirmation_node_labels)


@dataclass(frozen=True)
class CubeLibraryManagementService:
    """Provide UI-safe Cube Library management operations."""

    endpoint: ComfyEndpoint
    client: CubeLibraryClient

    def load_snapshot(self) -> CubeLibrarySnapshot:
        """Load target status, pack records, and read-only readiness."""

        status = self.client.get_status()
        if status is None or not status.available:
            return CubeLibrarySnapshot(
                endpoint=self.endpoint,
                status=status,
                packs=(),
                readiness=None,
                cube_paths_by_pack={},
            )
        packs = self.client.list_packs()
        return CubeLibrarySnapshot(
            endpoint=self.endpoint,
            status=status,
            packs=packs,
            readiness=self.client.get_dependency_readiness()
            or self.client.get_readiness(),
            cube_paths_by_pack=_cube_paths_by_pack(self.client.get_catalog()),
        )

    def preflight_pack(
        self,
        *,
        owner: str,
        repo: str,
        branch: str = "main",
    ) -> CubePackPreflight | None:
        """Preflight a candidate Cube Pack on the active target."""

        return self.client.preflight_pack(owner=owner, repo=repo, branch=branch)

    def add_pack(
        self,
        *,
        owner: str,
        repo: str,
        branch: str = "main",
        enabled: bool = True,
        auto_update: bool = False,
        sync_immediately: bool = True,
    ) -> CubePackRecord | None:
        """Track a Cube Pack on the active target."""

        return self.client.add_pack(
            owner=owner,
            repo=repo,
            branch=branch,
            enabled=enabled,
            auto_update=auto_update,
            sync_immediately=sync_immediately,
        )

    def set_pack_enabled(
        self,
        *,
        owner: str,
        repo: str,
        enabled: bool,
    ) -> CubePackRecord | None:
        """Enable or disable a tracked Cube Pack."""

        return self.client.update_pack(
            owner=owner,
            repo=repo,
            branch=None,
            enabled=enabled,
            auto_update=None,
        )

    def sync_pack(self, *, owner: str, repo: str) -> CubePackRecord | None:
        """Synchronously sync one tracked Cube Pack."""

        result = self.sync_and_check(
            CubeDependencySyncAndCheckRequest(
                sync_mode="pack",
                owner=owner,
                repo=repo,
            )
        )
        if result is not None:
            return self._pack_by_ref(f"{owner}/{repo}")
        return self.client.sync_pack(owner=owner, repo=repo)

    def sync_all_packs(self) -> tuple[CubePackRecord, ...]:
        """Synchronously sync all enabled Cube Packs."""

        result = self.sync_and_check(CubeDependencySyncAndCheckRequest(sync_mode="all"))
        if result is not None:
            return self.client.list_packs()
        return self.client.sync_all_packs()

    def remove_pack(self, *, owner: str, repo: str) -> bool:
        """Remove one tracked Cube Pack from the active target."""

        return self.client.remove_pack(owner=owner, repo=repo)

    def repair_dependencies(
        self,
        request: CubeDependencyRepairRequest,
    ) -> CubeDependencyRepairResult | None:
        """Repair approved dependency nodes through the active target."""

        return self.client.repair_dependencies(request)

    def sync_and_check(
        self,
        request: CubeDependencySyncAndCheckRequest,
    ) -> CubeDependencySyncAndCheckResult | None:
        """Run shared Cube Pack sync and dependency readiness orchestration."""

        return self.client.sync_and_check(request)

    def dependency_repair_proposal(
        self,
        readiness: object,
    ) -> CubeDependencyRepairProposal | None:
        """Return the repair proposal for one readiness report."""

        if not isinstance(readiness, CubeLibraryReadiness) or not readiness.can_install:
            return None
        installable_items = tuple(
            item
            for item in readiness.install_plan
            if item.installable and not item.installed
        )
        if not installable_items:
            return None
        confirmation_items = tuple(
            item for item in installable_items if item.confirmation_required
        )
        return CubeDependencyRepairProposal(
            baseline_only=not confirmation_items,
            approved_node_ids=tuple(item.node_id for item in installable_items),
            confirmation_node_labels=_dependency_node_labels(confirmation_items),
        )

    def repair_dependency_proposal(
        self,
        proposal: CubeDependencyRepairProposal,
    ) -> CubeDependencyRepairResult | None:
        """Repair dependency nodes selected by a proposal."""

        return self.repair_dependencies(
            CubeDependencyRepairRequest(
                baseline_only=proposal.baseline_only,
                approved_node_ids=proposal.approved_node_ids,
                sync_enabled_repos=False,
            )
        )

    def _pack_by_ref(self, repo_ref: str) -> CubePackRecord | None:
        """Return one refreshed pack by repository reference."""

        for pack in self.client.list_packs():
            if pack.repo_ref == repo_ref:
                return pack
        return None

    def recipe_drift_messages(
        self,
        buffers: Mapping[str, Mapping[str, object]],
    ) -> tuple[ApplicationText, ...]:
        """Return recipe cube availability notices for a recipe load."""

        catalog = self.client.get_catalog()
        if catalog is None:
            return ()

        catalog_by_cube_id = {entry.cube_id: entry for entry in catalog.cubes}
        messages: list[ApplicationText] = []
        for alias, buffer_data in buffers.items():
            cube_id = _string_value(buffer_data.get("cube_id"))
            if not cube_id:
                continue

            entry = catalog_by_cube_id.get(cube_id)
            label = _recipe_cube_label(alias, cube_id)
            if entry is None:
                messages.append(
                    app_text("%1 is not available in the active Cube Library.", label)
                )
                continue

            if entry.source.dirty:
                messages.append(
                    app_text(
                        "%1 currently has uncommitted Cube Library changes.", label
                    )
                )

        return tuple(messages)


def _string_value(value: object) -> str:
    """Return a stripped string value for recipe metadata comparison."""

    if not isinstance(value, str):
        return ""
    return value.strip()


def _recipe_cube_label(alias: str, cube_id: str) -> ApplicationText:
    """Return a concise recipe cube label for user-facing notices."""

    return app_text("Cube '%1' (%2)", alias, cube_id)


def _cube_paths_by_pack(catalog: object) -> dict[str, tuple[str, ...]]:
    """Return catalog cube paths grouped by source pack reference."""

    cubes = getattr(catalog, "cubes", None)
    if not isinstance(cubes, tuple):
        return {}
    grouped: dict[str, list[str]] = {}
    for entry in cubes:
        source = getattr(entry, "source", None)
        repo_ref = getattr(source, "repo_ref", "")
        path = getattr(source, "path", "")
        if isinstance(repo_ref, str) and repo_ref and isinstance(path, str) and path:
            grouped.setdefault(repo_ref, []).append(path)
    return {repo_ref: tuple(sorted(paths)) for repo_ref, paths in grouped.items()}


def _dependency_node_labels(
    items: tuple[CubeDependencyInstallPlanItem, ...],
) -> tuple[str, ...]:
    """Return display labels for dependency repair confirmation."""

    return tuple(f"{item.display_name} ({item.node_id})" for item in items)
