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

"""Orchestrate Registry-first reconciliation of Substitute core nodepacks."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from pathlib import Path

from substitute.application.comfy_nodepacks.core_nodepack_reconciliation_plan import (
    CoreNodepackAction,
    plan_after_registry_attempt,
    plan_initial_reconciliation,
)
from substitute.domain.comfy_nodepacks import CoreNodepackId, NodepackManagementKind
from substitute.infrastructure.comfy.legacy_nodepack_distribution import (
    LegacyNodepackDistributionCleaner,
)
from substitute.infrastructure.comfy.local_nodepack_source import (
    copy_local_nodepack_source,
    resolve_local_nodepack_source,
)
from substitute.infrastructure.comfy.nodepack_installation_inspector import (
    NodepackInstallationInspector,
    NodepackInstallationSnapshot,
)
from substitute.infrastructure.comfy.nodepack_installation_path_migrator import (
    canonicalize_nodepack_root,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    CORE_COMFY_NODEPACKS,
    CoreComfyNodepack,
)
from substitute.infrastructure.comfy.nodepack_python_dependencies import (
    install_nodepack_python_dependencies,
    nodepack_python_dependencies_satisfied,
)
from substitute.infrastructure.comfy.nodepack_reconciliation_logger import LogCallback
from substitute.infrastructure.comfy.nodepack_registry_installer import (
    ComfyNodepackRegistryInstaller,
)
from substitute.infrastructure.comfy.nodepack_registry_source_migrator import (
    NodepackRegistrySourceMigrator,
)
from substitute.infrastructure.comfy.nodepack_registry_update_settler import (
    ComfyNodepackRegistryUpdateSettler,
)
from substitute.infrastructure.comfy.pinned_nodepack_source import (
    PinnedNodepackSourceInstaller,
)
from substitute.infrastructure.comfy.workspace_python_resolver import (
    resolve_workspace_python,
)
from substitute.infrastructure.version_control import (
    RepositoryService,
    repository_service,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("infrastructure.comfy.core_nodepack_reconciler")


class CoreNodepackReconciler:
    """Coordinate focused owners without duplicating their policy or mechanics."""

    def __init__(
        self,
        *,
        repositories: RepositoryService,
        registry_installer: ComfyNodepackRegistryInstaller | None = None,
        registry_update_settler: ComfyNodepackRegistryUpdateSettler | None = None,
        source_migrator: NodepackRegistrySourceMigrator | None = None,
        fallback_installer: PinnedNodepackSourceInstaller | None = None,
        legacy_cleaner: LegacyNodepackDistributionCleaner | None = None,
    ) -> None:
        """Compose the focused owners used by nodepack reconciliation."""

        self._inspector = NodepackInstallationInspector(repositories)
        self._registry = registry_installer or ComfyNodepackRegistryInstaller()
        self._registry_update_settler = (
            registry_update_settler or ComfyNodepackRegistryUpdateSettler()
        )
        self._source_migrator = source_migrator or NodepackRegistrySourceMigrator(
            repositories
        )
        self._fallback = fallback_installer or PinnedNodepackSourceInstaller()
        self._legacy_cleaner = legacy_cleaner or LegacyNodepackDistributionCleaner()

    def ensure(
        self,
        workspace: Path,
        *,
        python_executable: Path,
        refresh_nodepacks: Collection[CoreNodepackId],
        on_log: LogCallback | None,
        env: Mapping[str, str] | None,
    ) -> None:
        """Converge every required nodepack through the Registry-first policy."""

        refresh_targets = frozenset(refresh_nodepacks)
        for nodepack in CORE_COMFY_NODEPACKS:
            self._ensure_one(
                workspace=workspace,
                python_executable=python_executable,
                nodepack=nodepack,
                refresh_requested=nodepack.nodepack_id in refresh_targets,
                on_log=on_log,
                env=env,
            )

    def _ensure_one(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        nodepack: CoreComfyNodepack,
        refresh_requested: bool,
        on_log: LogCallback | None,
        env: Mapping[str, str] | None,
    ) -> None:
        """Converge one nodepack while preserving its mutable installed state."""

        snapshot = self._inspector.inspect(workspace=workspace, nodepack=nodepack)
        local_source = resolve_local_nodepack_source(nodepack, env=env)
        action = plan_initial_reconciliation(
            management=snapshot.management,
            matches_required_version=snapshot.matches(nodepack),
            tracked_worktree_dirty=snapshot.tracked_worktree_dirty,
            official_git_remote=snapshot.official_git_remote,
            local_source_configured=local_source is not None,
            refresh_requested=refresh_requested,
        )
        if action is CoreNodepackAction.USE_LOCAL_SOURCE:
            assert local_source is not None
            self._use_local_source(
                source_path=local_source,
                snapshot=snapshot,
                nodepack=nodepack,
                python_executable=python_executable,
                on_log=on_log,
                env=env,
            )
            return
        if action is CoreNodepackAction.BLOCK_DIRTY:
            raise RuntimeError(
                f"{nodepack.display_name} contains tracked local changes and does not "
                f"match required version {nodepack.required_version}. Preserve or "
                "publish those changes before managed repair."
            )
        if action is CoreNodepackAction.BLOCK_UNMANAGED_GIT:
            raise RuntimeError(
                f"{nodepack.display_name} is a non-managed Git checkout and does not "
                f"match required version {nodepack.required_version}. Configure its "
                "local source environment variable or install the required release."
            )
        changed = False
        if snapshot.management is NodepackManagementKind.REGISTRY:
            canonical_root = canonicalize_nodepack_root(
                workspace=workspace,
                current_root=snapshot.root,
                nodepack=nodepack,
                on_log=on_log,
            )
            if canonical_root.name != snapshot.root.name:
                changed = True
                snapshot = self._inspector.inspect(
                    workspace=workspace,
                    nodepack=nodepack,
                )
        if action is CoreNodepackAction.MIGRATE_GIT:
            self._source_migrator.migrate_clean_git_installation(
                target_path=snapshot.root,
                nodepack=nodepack,
                on_log=on_log,
            )
            canonicalize_nodepack_root(
                workspace=workspace,
                current_root=snapshot.root,
                nodepack=nodepack,
                on_log=on_log,
            )
            changed = True
            snapshot = self._inspector.inspect(workspace=workspace, nodepack=nodepack)
            action = plan_initial_reconciliation(
                management=snapshot.management,
                matches_required_version=snapshot.matches(nodepack),
                tracked_worktree_dirty=False,
                official_git_remote=False,
                local_source_configured=False,
                refresh_requested=refresh_requested,
            )
        elif action is CoreNodepackAction.INSTALL_REGISTRY and (
            snapshot.management is NodepackManagementKind.PLAIN
        ):
            if snapshot.project_name is None or not snapshot.sentinels_present:
                raise RuntimeError(
                    f"Refusing to overwrite unrecognized nodepack folder: {snapshot.root}"
                )
            self._source_migrator.migrate_plain_installation(
                target_path=snapshot.root,
                nodepack=nodepack,
                on_log=on_log,
            )
            canonicalize_nodepack_root(
                workspace=workspace,
                current_root=snapshot.root,
                nodepack=nodepack,
                on_log=on_log,
            )
            changed = True
            snapshot = self._inspector.inspect(workspace=workspace, nodepack=nodepack)
        if action is CoreNodepackAction.INSTALL_REGISTRY:
            registry_result = self._registry.install_exact(
                workspace=workspace,
                python_executable=python_executable,
                nodepack=nodepack,
                on_log=on_log,
                env=env,
            )
            snapshot = self._inspector.inspect(workspace=workspace, nodepack=nodepack)
            action = plan_after_registry_attempt(
                outcome=registry_result.outcome,
                registry_installation_matches=(
                    snapshot.management is NodepackManagementKind.REGISTRY
                    and snapshot.matches(nodepack)
                ),
            )
            changed = True
        if action is CoreNodepackAction.SETTLE_REGISTRY_UPDATE:
            self._registry_update_settler.settle(
                workspace=workspace,
                python_executable=python_executable,
                nodepack=nodepack,
                on_log=on_log,
                env=env,
            )
            snapshot = self._inspector.inspect(workspace=workspace, nodepack=nodepack)
            action = (
                CoreNodepackAction.READY
                if snapshot.management is NodepackManagementKind.REGISTRY
                and snapshot.matches(nodepack)
                else CoreNodepackAction.FAIL
            )
        if action is CoreNodepackAction.INSTALL_FALLBACK:
            self._fallback.install_fallback(
                target_path=snapshot.root,
                nodepack=nodepack,
                on_log=on_log,
                env=env,
            )
            snapshot = self._inspector.inspect(workspace=workspace, nodepack=nodepack)
            changed = True
            action = (
                CoreNodepackAction.READY
                if snapshot.management is NodepackManagementKind.REGISTRY
                and snapshot.matches(nodepack)
                else CoreNodepackAction.FAIL
            )
        if action is not CoreNodepackAction.READY:
            raise RuntimeError(
                f"Could not install {nodepack.display_name} "
                f"{nodepack.required_version} through Comfy Registry or its pinned fallback."
            )
        self._finish_ready_installation(
            python_executable=python_executable,
            snapshot=snapshot,
            nodepack=nodepack,
            source_changed=changed,
            on_log=on_log,
            env=env,
        )

    def _use_local_source(
        self,
        *,
        source_path: Path,
        snapshot: NodepackInstallationSnapshot,
        nodepack: CoreComfyNodepack,
        python_executable: Path,
        on_log: LogCallback | None,
        env: Mapping[str, str] | None,
    ) -> None:
        """Project an explicit developer source without handing it to Registry updates."""

        target_path = snapshot.root
        if source_path.resolve() != target_path.resolve():
            copy_local_nodepack_source(
                source_path=source_path,
                target_path=target_path,
                allow_existing=target_path.exists(),
            )
        install_nodepack_python_dependencies(
            python_executable=python_executable,
            nodepack_root=target_path,
            display_name=nodepack.display_name,
            on_log=on_log,
            env=env,
        )
        _emit_ready(on_log, nodepack, source="local")

    def _finish_ready_installation(
        self,
        *,
        python_executable: Path,
        snapshot: NodepackInstallationSnapshot,
        nodepack: CoreComfyNodepack,
        source_changed: bool,
        on_log: LogCallback | None,
        env: Mapping[str, str] | None,
    ) -> None:
        """Remove legacy duplication and ensure declared dependencies are satisfied."""

        legacy_removed = self._legacy_cleaner.remove_if_owned(
            python_executable=python_executable,
            nodepack_root=snapshot.root,
            distribution_name=nodepack.legacy_distribution_name,
            on_log=on_log,
            env=env,
        )
        dependencies_ready = nodepack_python_dependencies_satisfied(
            python_executable=python_executable,
            nodepack_root=snapshot.root,
            env=env,
        )
        if source_changed or legacy_removed or not dependencies_ready:
            install_nodepack_python_dependencies(
                python_executable=python_executable,
                nodepack_root=snapshot.root,
                display_name=nodepack.display_name,
                on_log=on_log,
                env=env,
            )
        _emit_ready(on_log, nodepack, source="registry")


def ensure_core_comfy_nodepacks(
    workspace: Path,
    *,
    refresh_nodepacks: Collection[CoreNodepackId] = frozenset(),
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
    python_executable: Path | None = None,
    repositories: RepositoryService | None = None,
) -> None:
    """Ensure required core nodepacks through the production composition."""

    resolved_python = python_executable or resolve_workspace_python(workspace)
    CoreNodepackReconciler(repositories=repositories or repository_service()).ensure(
        workspace,
        python_executable=resolved_python,
        refresh_nodepacks=refresh_nodepacks,
        on_log=on_log,
        env=env,
    )


def refresh_core_comfy_nodepacks(
    workspace: Path,
    *,
    nodepacks: Collection[CoreNodepackId],
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Refresh selected core nodepacks through Registry-first reconciliation."""

    ensure_core_comfy_nodepacks(
        workspace,
        refresh_nodepacks=nodepacks,
        on_log=on_log,
        env=env,
    )


def _emit_ready(
    callback: LogCallback | None,
    nodepack: CoreComfyNodepack,
    *,
    source: str,
) -> None:
    """Emit one bounded ready-state event."""

    message = (
        f"[ComfyNodepacks] {nodepack.display_name} "
        f"{nodepack.required_version} is ready."
    )
    log_info(
        _LOGGER,
        message,
        nodepack_id=nodepack.nodepack_id.value,
        required_version=nodepack.required_version,
        source=source,
    )
    if callback is not None:
        callback(message)


__all__ = [
    "CoreNodepackReconciler",
    "ensure_core_comfy_nodepacks",
    "refresh_core_comfy_nodepacks",
]
