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

"""Install and refresh core Comfy nodepacks required by Substitute."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from pathlib import Path

from substitute.application.comfy_nodepacks.core_nodepack_reconciliation_plan import (
    plan_core_nodepack_dependency_refresh,
    plan_core_nodepack_install_route,
    plan_core_nodepack_refresh_route,
)
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.infrastructure.comfy.comfy_cli_adapter import ComfyCliWorkspaceAdapter
from substitute.infrastructure.comfy.local_nodepack_source import (
    copy_local_nodepack_source,
    resolve_local_nodepack_source,
)
from substitute.infrastructure.comfy.nodepack_git_maintenance import (
    refresh_git_nodepack as _refresh_git_nodepack,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    CORE_COMFY_NODEPACKS,
    CoreComfyNodepack,
)
from substitute.infrastructure.comfy.nodepack_python_dependencies import (
    install_backend_python_dependencies,
    install_sugarcubes_python_dependencies,
    python_distribution_satisfies_minimum as _python_distribution_satisfies_minimum,
    remove_noncanonical_python_distribution_metadata as _remove_noncanonical_python_distribution_metadata,
)
from substitute.infrastructure.comfy.nodepack_reconciliation_logger import (
    LogCallback,
    emit_log as _emit_log,
)
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    core_nodepack_installed,
    nodepack_has_git_metadata as _nodepack_has_git_metadata,
)
from substitute.infrastructure.comfy.pinned_nodepack_source import (
    apply_pinned_source_fallback as _apply_pinned_source_fallback,
    replace_with_pinned_source_archive as _replace_with_pinned_source_archive,
)
from substitute.infrastructure.comfy.workspace_python_resolver import (
    resolve_workspace_python,
)

DependencyInstaller = Callable[..., None]


def ensure_core_comfy_nodepacks(
    workspace: Path,
    *,
    refresh_nodepacks: Collection[CoreNodepackId] = frozenset(),
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
    python_executable: Path | None = None,
) -> None:
    """Ensure Substitute's required Comfy nodepacks are installed and current."""

    if python_executable is None:
        python_executable = resolve_workspace_python(workspace)
    adapter = ComfyCliWorkspaceAdapter(
        workspace=workspace,
        python_executable=python_executable,
        on_log=on_log,
        env=env,
    )
    adapter.ensure_available()
    refresh_targets = frozenset(refresh_nodepacks)
    for nodepack in CORE_COMFY_NODEPACKS:
        if core_nodepack_installed(workspace, nodepack):
            if nodepack.nodepack_id in refresh_targets:
                _emit_log(
                    on_log,
                    f"[ComfyNodepacks] Refreshing {nodepack.display_name}.",
                    operation="core_nodepack_refresh",
                    nodepack_id=nodepack.nodepack_id.value,
                    display_name=nodepack.display_name,
                    registry_id=nodepack.registry_id,
                )
                _refresh_core_nodepack(adapter, nodepack, on_log=on_log, env=env)
                if not core_nodepack_installed(workspace, nodepack):
                    raise RuntimeError(
                        f"{nodepack.display_name} refresh finished, but sentinels are missing."
                    )
                _refresh_nodepack_python_dependencies(
                    python_executable=python_executable,
                    workspace=workspace,
                    nodepack=nodepack,
                    on_log=on_log,
                    env=env,
                )
            else:
                if _installed_core_nodepack_satisfies_minimum(
                    python_executable=python_executable,
                    workspace=workspace,
                    nodepack=nodepack,
                    on_log=on_log,
                    env=env,
                ):
                    _emit_log(
                        on_log,
                        f"[ComfyNodepacks] {nodepack.display_name} is installed.",
                        operation="core_nodepack_ready",
                        nodepack_id=nodepack.nodepack_id.value,
                        display_name=nodepack.display_name,
                        registry_id=nodepack.registry_id,
                    )
                else:
                    _emit_log(
                        on_log,
                        (
                            f"[ComfyNodepacks] {nodepack.display_name} is installed "
                            "but below the required version; refreshing before launch."
                        ),
                        operation="core_nodepack_dependency_refresh",
                        nodepack_id=nodepack.nodepack_id.value,
                        display_name=nodepack.display_name,
                        registry_id=nodepack.registry_id,
                    )
                    _refresh_nodepack_python_dependencies(
                        python_executable=python_executable,
                        workspace=workspace,
                        nodepack=nodepack,
                        on_log=on_log,
                        env=env,
                    )
            continue
        _emit_log(
            on_log,
            f"[ComfyNodepacks] Installing {nodepack.display_name} through Comfy CLI.",
            operation="core_nodepack_install",
            nodepack_id=nodepack.nodepack_id.value,
            display_name=nodepack.display_name,
            registry_id=nodepack.registry_id,
        )
        _install_core_nodepack(adapter, nodepack, on_log=on_log)
        if not core_nodepack_installed(workspace, nodepack):
            raise RuntimeError(
                f"Comfy CLI finished, but {nodepack.display_name} is still missing."
            )
        _refresh_nodepack_python_dependencies(
            python_executable=python_executable,
            workspace=workspace,
            nodepack=nodepack,
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
    """Refresh installed core nodepacks during managed repair."""

    ensure_core_comfy_nodepacks(
        workspace,
        refresh_nodepacks=nodepacks,
        on_log=on_log,
        env=env,
    )


def _installed_core_nodepack_satisfies_minimum(
    *,
    python_executable: Path,
    workspace: Path,
    nodepack: CoreComfyNodepack,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> bool:
    """Return whether an installed core nodepack satisfies its package contract."""

    return _nodepack_python_distributions_satisfy_minimum(
        python_executable=python_executable,
        cwd=workspace / nodepack.expected_folder,
        nodepack=nodepack,
        on_log=on_log,
        env=env,
    )


def _install_core_nodepack(
    adapter: ComfyCliWorkspaceAdapter,
    nodepack: CoreComfyNodepack,
    *,
    on_log: LogCallback | None,
) -> None:
    """Install one core nodepack with registry, URL, then local-source fallbacks."""

    registry_available = adapter.manager_knows_node(nodepack.registry_id)
    source_path = (
        None
        if registry_available or nodepack.source_url is not None
        else resolve_local_nodepack_source(nodepack)
    )
    route = plan_core_nodepack_install_route(
        registry_id=nodepack.registry_id,
        registry_available=registry_available,
        source_url=nodepack.source_url,
        local_source_available=source_path is not None,
    )
    if route.source == "registry":
        if route.install_id is None:
            raise RuntimeError(
                f"Could not install required nodepack: {nodepack.display_name}"
            )
        adapter.install_node(route.install_id)
        return
    _emit_log(
        on_log,
        (
            f"[ComfyNodepacks] {nodepack.registry_id} is not in this Comfy Manager "
            "node list."
        ),
        operation="core_nodepack_install_registry_miss",
        nodepack_id=nodepack.nodepack_id.value,
        display_name=nodepack.display_name,
        registry_id=nodepack.registry_id,
    )
    if route.source == "source_url":
        if route.install_id is None:
            raise RuntimeError(
                f"Could not install required nodepack: {nodepack.display_name}"
            )
        _emit_log(
            on_log,
            (
                f"[ComfyNodepacks] Installing {nodepack.display_name} from "
                f"{route.install_id}."
            ),
            operation="core_nodepack_install_source_fallback",
            nodepack_id=nodepack.nodepack_id.value,
            display_name=nodepack.display_name,
            registry_id=nodepack.registry_id,
            source_kind="github",
        )
        adapter.install_node(route.install_id)
        return
    if route.source == "local_source":
        if source_path is None:
            raise RuntimeError(
                f"Could not install required nodepack: {nodepack.display_name}"
            )
        _emit_log(
            on_log,
            (
                f"[ComfyNodepacks] Installing {nodepack.display_name} from local "
                f"source {source_path}."
            ),
            operation="core_nodepack_install_source_fallback",
            nodepack_id=nodepack.nodepack_id.value,
            display_name=nodepack.display_name,
            registry_id=nodepack.registry_id,
            source_kind="local",
        )
        copy_local_nodepack_source(
            source_path=source_path,
            target_path=adapter.workspace / nodepack.expected_folder,
        )
        return
    _emit_log(
        on_log,
        (
            f"[ComfyNodepacks] {nodepack.display_name} is not published in this "
            "Comfy Manager node list and no GitHub or local source fallback is available."
        ),
        operation="core_nodepack_install_failed",
        nodepack_id=nodepack.nodepack_id.value,
        display_name=nodepack.display_name,
        registry_id=nodepack.registry_id,
    )
    raise RuntimeError(f"Could not install required nodepack: {nodepack.display_name}")


def _refresh_core_nodepack(
    adapter: ComfyCliWorkspaceAdapter,
    nodepack: CoreComfyNodepack,
    *,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> None:
    """Refresh one existing core nodepack using managed ownership rules."""

    target_path = adapter.workspace / nodepack.expected_folder
    git_managed = _nodepack_has_git_metadata(target_path)
    refresh_route = plan_core_nodepack_refresh_route(
        registry_id=nodepack.registry_id,
        git_managed=git_managed,
        git_refresh_succeeded=None,
        pinned_archive_available=nodepack.pinned_source_archive_url is not None,
        registry_available=False,
        source_url=nodepack.source_url,
        local_source_available=False,
    )
    if refresh_route.source == "git_refresh":
        git_refresh_succeeded = _refresh_git_nodepack(
            target_path, on_log=on_log, env=env
        )
        if git_refresh_succeeded:
            return
        refresh_route = plan_core_nodepack_refresh_route(
            registry_id=nodepack.registry_id,
            git_managed=git_managed,
            git_refresh_succeeded=False,
            pinned_archive_available=nodepack.pinned_source_archive_url is not None,
            registry_available=False,
            source_url=nodepack.source_url,
            local_source_available=False,
        )
        if refresh_route.source == "pinned_archive":
            if nodepack.pinned_source_archive_url is None:
                raise RuntimeError(
                    f"Could not refresh required nodepack: {nodepack.display_name}"
                )
            _replace_with_pinned_source_archive(
                archive_url=nodepack.pinned_source_archive_url,
                target_path=target_path,
                nodepack=nodepack,
                on_log=on_log,
                env=env,
            )
            return
    registry_available = adapter.manager_knows_node(nodepack.registry_id)
    source_path = (
        None
        if registry_available or nodepack.source_url is not None
        else resolve_local_nodepack_source(nodepack)
    )
    refresh_route = plan_core_nodepack_refresh_route(
        registry_id=nodepack.registry_id,
        git_managed=git_managed,
        git_refresh_succeeded=False if git_managed else None,
        pinned_archive_available=nodepack.pinned_source_archive_url is not None,
        registry_available=registry_available,
        source_url=nodepack.source_url,
        local_source_available=source_path is not None,
    )
    if refresh_route.source == "registry":
        if refresh_route.install_id is None:
            raise RuntimeError(
                f"Could not refresh required nodepack: {nodepack.display_name}"
            )
        adapter.install_node(refresh_route.install_id)
        return
    if refresh_route.source == "source_url":
        if refresh_route.install_id is None:
            raise RuntimeError(
                f"Could not refresh required nodepack: {nodepack.display_name}"
            )
        adapter.install_node(refresh_route.install_id)
        return
    if refresh_route.source == "local_source":
        if source_path is None:
            raise RuntimeError(
                f"Could not refresh required nodepack: {nodepack.display_name}"
            )
        _emit_log(
            on_log,
            (
                f"[ComfyNodepacks] Overlaying {nodepack.display_name} from local "
                f"source {source_path}."
            ),
            operation="core_nodepack_refresh_source_fallback",
            nodepack_id=nodepack.nodepack_id.value,
            display_name=nodepack.display_name,
            registry_id=nodepack.registry_id,
            source_kind="local",
        )
        copy_local_nodepack_source(
            source_path=source_path,
            target_path=target_path,
            allow_existing=True,
        )
        return
    raise RuntimeError(f"Could not refresh required nodepack: {nodepack.display_name}")


def _refresh_nodepack_python_dependencies(
    *,
    python_executable: Path,
    workspace: Path,
    nodepack: CoreComfyNodepack,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> None:
    """Refresh Python dependencies for nodepacks that own runtime packages."""

    if nodepack.nodepack_id is CoreNodepackId.SUBSTITUTE_BACKEND:
        _refresh_python_distribution_nodepack_dependencies(
            python_executable=python_executable,
            workspace=workspace,
            nodepack=nodepack,
            on_log=on_log,
            env=env,
            install_dependencies=install_backend_python_dependencies,
        )
        return
    if nodepack.nodepack_id is CoreNodepackId.SUGARCUBES:
        _refresh_python_distribution_nodepack_dependencies(
            python_executable=python_executable,
            workspace=workspace,
            nodepack=nodepack,
            on_log=on_log,
            env=env,
            install_dependencies=install_sugarcubes_python_dependencies,
        )


def _refresh_python_distribution_nodepack_dependencies(
    *,
    python_executable: Path,
    workspace: Path,
    nodepack: CoreComfyNodepack,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
    install_dependencies: DependencyInstaller,
) -> None:
    """Refresh editable nodepack dependencies and apply pinned fallback when needed."""

    nodepack_root = workspace / nodepack.expected_folder
    _remove_noncanonical_python_distribution_metadata(
        nodepack_root=nodepack_root,
        nodepack=nodepack,
        on_log=on_log,
    )
    install_dependencies(
        python_executable=python_executable,
        nodepack_root=nodepack_root,
        on_log=on_log,
        env=env,
    )
    _remove_noncanonical_python_distribution_metadata(
        nodepack_root=nodepack_root,
        nodepack=nodepack,
        on_log=on_log,
    )
    primary_minimum_satisfied = _nodepack_python_distributions_satisfy_minimum(
        python_executable=python_executable,
        cwd=nodepack_root,
        nodepack=nodepack,
        on_log=on_log,
        env=env,
    )
    dependency_plan = plan_core_nodepack_dependency_refresh(
        minimum_satisfied=primary_minimum_satisfied,
        pinned_archive_available=nodepack.pinned_source_archive_url is not None,
        pinned_fallback_already_applied=False,
    )
    if dependency_plan.action == "ready":
        return
    if dependency_plan.action == "failed":
        raise RuntimeError(
            f"{nodepack.display_name} dependency refresh did not install the required version."
        )
    if nodepack.pinned_source_archive_url is None:
        raise RuntimeError(
            f"{nodepack.display_name} dependency refresh did not install the required version."
        )
    _emit_log(
        on_log,
        (
            f"[ComfyNodepacks] Registry refresh did not provide "
            f"{nodepack.display_name} {nodepack.minimum_python_distribution_version}; "
            "applying pinned GitHub fallback while preserving nodepack metadata shape."
        ),
        operation="core_nodepack_dependency_pinned_fallback",
        nodepack_id=nodepack.nodepack_id.value,
        display_name=nodepack.display_name,
        registry_id=nodepack.registry_id,
        required_version=nodepack.minimum_python_distribution_version,
        fallback_kind="pinned_archive",
    )
    _apply_pinned_source_fallback(
        backend_root=nodepack_root,
        archive_url=nodepack.pinned_source_archive_url,
        target_path=nodepack_root,
        nodepack=nodepack,
        on_log=on_log,
        env=env,
    )
    install_dependencies(
        python_executable=python_executable,
        nodepack_root=nodepack_root,
        on_log=on_log,
        env=env,
    )
    _remove_noncanonical_python_distribution_metadata(
        nodepack_root=nodepack_root,
        nodepack=nodepack,
        on_log=on_log,
    )
    fallback_minimum_satisfied = _nodepack_python_distributions_satisfy_minimum(
        python_executable=python_executable,
        cwd=nodepack_root,
        nodepack=nodepack,
        on_log=on_log,
        env=env,
    )
    dependency_plan = plan_core_nodepack_dependency_refresh(
        minimum_satisfied=fallback_minimum_satisfied,
        pinned_archive_available=nodepack.pinned_source_archive_url is not None,
        pinned_fallback_already_applied=True,
    )
    if dependency_plan.action == "failed":
        raise RuntimeError(
            f"Could not install {nodepack.display_name} "
            f"{nodepack.minimum_python_distribution_version} from fallback source."
        )


def _nodepack_python_distributions_satisfy_minimum(
    *,
    python_executable: Path,
    cwd: Path,
    nodepack: CoreComfyNodepack,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> bool:
    """Return whether the canonical Python distribution satisfies the nodepack contract."""

    return _python_distribution_satisfies_minimum(
        python_executable=python_executable,
        cwd=cwd,
        distribution_name=nodepack.python_distribution_name,
        minimum_version=nodepack.minimum_python_distribution_version,
        on_log=on_log,
        env=env,
    )


__all__ = [
    "ensure_core_comfy_nodepacks",
    "refresh_core_comfy_nodepacks",
]
