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

"""Plan pure core nodepack reconciliation decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CoreNodepackRefreshSource = Literal[
    "git_refresh",
    "git_refreshed",
    "pinned_archive",
    "registry",
    "source_url",
    "local_source",
    "unavailable",
]
CoreNodepackDependencyRefreshAction = Literal[
    "ready",
    "pinned_fallback",
    "failed",
]


@dataclass(frozen=True)
class CoreNodepackRefreshRoute:
    """Describe the selected source for refreshing one core nodepack."""

    source: CoreNodepackRefreshSource
    install_id: str | None


@dataclass(frozen=True)
class CoreNodepackDependencyRefreshPlan:
    """Describe the next dependency-refresh action for one core nodepack."""

    action: CoreNodepackDependencyRefreshAction


def plan_core_nodepack_refresh_route(
    *,
    registry_id: str,
    git_managed: bool,
    git_refresh_succeeded: bool | None,
    pinned_archive_available: bool,
    registry_available: bool,
    source_url: str | None,
    local_source_available: bool,
) -> CoreNodepackRefreshRoute:
    """Return the refresh source selected from known nodepack availability facts."""

    if git_managed and git_refresh_succeeded is None:
        return CoreNodepackRefreshRoute(source="git_refresh", install_id=None)
    if git_managed and git_refresh_succeeded is True:
        return CoreNodepackRefreshRoute(source="git_refreshed", install_id=None)
    if git_managed and git_refresh_succeeded is False and pinned_archive_available:
        return CoreNodepackRefreshRoute(source="pinned_archive", install_id=None)
    if registry_available:
        return CoreNodepackRefreshRoute(source="registry", install_id=registry_id)
    if source_url is not None:
        return CoreNodepackRefreshRoute(source="source_url", install_id=source_url)
    if local_source_available:
        return CoreNodepackRefreshRoute(source="local_source", install_id=None)
    return CoreNodepackRefreshRoute(source="unavailable", install_id=None)


def plan_core_nodepack_dependency_refresh(
    *,
    minimum_satisfied: bool,
    pinned_archive_available: bool,
    pinned_fallback_already_applied: bool,
) -> CoreNodepackDependencyRefreshPlan:
    """Return the next dependency-refresh action from version and fallback facts."""

    if minimum_satisfied:
        return CoreNodepackDependencyRefreshPlan(action="ready")
    if pinned_archive_available and not pinned_fallback_already_applied:
        return CoreNodepackDependencyRefreshPlan(action="pinned_fallback")
    return CoreNodepackDependencyRefreshPlan(action="failed")


__all__ = [
    "CoreNodepackDependencyRefreshAction",
    "CoreNodepackDependencyRefreshPlan",
    "CoreNodepackRefreshRoute",
    "CoreNodepackRefreshSource",
    "plan_core_nodepack_dependency_refresh",
    "plan_core_nodepack_refresh_route",
]
