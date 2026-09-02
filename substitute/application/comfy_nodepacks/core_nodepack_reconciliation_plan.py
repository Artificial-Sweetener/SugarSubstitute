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

"""Plan pure Registry-first core nodepack reconciliation decisions."""

from __future__ import annotations

from enum import Enum

from substitute.domain.comfy_nodepacks import NodepackManagementKind


class CoreNodepackAction(str, Enum):
    """Describe the next effect required for one core nodepack."""

    READY = "ready"
    USE_LOCAL_SOURCE = "use_local_source"
    MIGRATE_GIT = "migrate_git"
    INSTALL_REGISTRY = "install_registry"
    SETTLE_REGISTRY_UPDATE = "settle_registry_update"
    INSTALL_FALLBACK = "install_fallback"
    BLOCK_DIRTY = "block_dirty"
    BLOCK_UNMANAGED_GIT = "block_unmanaged_git"
    FAIL = "fail"


class RegistryInstallOutcome(str, Enum):
    """Classify one exact-version Comfy Registry installation attempt."""

    INSTALLED = "installed"
    ALREADY_INSTALLED = "already_installed"
    PENDING_STARTUP = "pending_startup"
    VERSION_UNAVAILABLE = "version_unavailable"
    REGISTRY_UNREACHABLE = "registry_unreachable"
    FAILED = "failed"


def plan_initial_reconciliation(
    *,
    management: NodepackManagementKind,
    matches_required_version: bool,
    tracked_worktree_dirty: bool,
    official_git_remote: bool,
    local_source_configured: bool,
    refresh_requested: bool,
) -> CoreNodepackAction:
    """Select the first action from installed source and ownership evidence."""

    if local_source_configured:
        return CoreNodepackAction.USE_LOCAL_SOURCE
    if management is NodepackManagementKind.GIT:
        if tracked_worktree_dirty:
            return (
                CoreNodepackAction.READY
                if matches_required_version
                else CoreNodepackAction.BLOCK_DIRTY
            )
        if not official_git_remote:
            return (
                CoreNodepackAction.READY
                if matches_required_version
                else CoreNodepackAction.BLOCK_UNMANAGED_GIT
            )
        return CoreNodepackAction.MIGRATE_GIT
    if (
        management is NodepackManagementKind.REGISTRY
        and matches_required_version
        and not refresh_requested
    ):
        return CoreNodepackAction.READY
    return CoreNodepackAction.INSTALL_REGISTRY


def plan_after_registry_attempt(
    *,
    outcome: RegistryInstallOutcome,
    registry_installation_matches: bool,
) -> CoreNodepackAction:
    """Select completion or fallback from Registry outcome and disk evidence."""

    if registry_installation_matches:
        return CoreNodepackAction.READY
    if outcome is RegistryInstallOutcome.PENDING_STARTUP:
        return CoreNodepackAction.SETTLE_REGISTRY_UPDATE
    if outcome in {
        RegistryInstallOutcome.VERSION_UNAVAILABLE,
        RegistryInstallOutcome.REGISTRY_UNREACHABLE,
        RegistryInstallOutcome.FAILED,
    }:
        return CoreNodepackAction.INSTALL_FALLBACK
    return CoreNodepackAction.FAIL


__all__ = [
    "CoreNodepackAction",
    "RegistryInstallOutcome",
    "plan_after_registry_attempt",
    "plan_initial_reconciliation",
]
