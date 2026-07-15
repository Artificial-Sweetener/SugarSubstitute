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

"""Project Cube Library records into settings-facing display models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from substitute.application.cube_library.service import CubeLibrarySnapshot
from substitute.domain.cube_library import CubeLibraryReadiness, CubePackRecord

BadgeSeverity = Literal["neutral", "success", "warning", "error"]

BASE_PACK_REMOVE_DISABLED_REASON = (
    "Base Cube Packs are required by Substitute and cannot be removed."
)


@dataclass(frozen=True)
class CubeLibraryStatusView:
    """Describe the active target status row for Cube Library settings."""

    available: bool
    description: str
    can_sync_all: bool


@dataclass(frozen=True)
class CubePackBadgeView:
    """Describe one compact state badge for a tracked Cube Pack."""

    text: str
    severity: BadgeSeverity


@dataclass(frozen=True)
class CubePackDetailView:
    """Describe one label/value row in an expanded Cube Pack."""

    label: str
    value: str
    severity: BadgeSeverity = "neutral"
    visible: bool = True


@dataclass(frozen=True)
class CubePackRowView:
    """Describe one tracked Cube Pack row for Settings presentation."""

    repo_ref: str
    owner: str
    repo: str
    title: str
    subtitle: str
    badges: tuple[CubePackBadgeView, ...]
    enabled: bool
    can_remove: bool
    remove_disabled_reason: str
    details: tuple[CubePackDetailView, ...]


@dataclass(frozen=True)
class CubeLibraryReadinessView:
    """Describe target readiness for Settings presentation."""

    ready: bool
    title: str
    summary: str
    details: tuple[CubePackDetailView, ...]


def project_library_status(
    snapshot: CubeLibrarySnapshot | None,
) -> CubeLibraryStatusView:
    """Return a display model for the Cube Library status card."""

    if snapshot is None:
        return CubeLibraryStatusView(
            available=False,
            description="Cube Library unavailable on the active target.",
            can_sync_all=False,
        )
    if not snapshot.available:
        return CubeLibraryStatusView(
            available=False,
            description="Cube Library unavailable on the active target.",
            can_sync_all=False,
        )
    target = f"{snapshot.endpoint.host}:{snapshot.endpoint.port}"
    return CubeLibraryStatusView(
        available=True,
        description=f"Connected to {target}.",
        can_sync_all=any(pack.enabled for pack in snapshot.packs),
    )


def project_pack(
    pack: CubePackRecord,
    *,
    cube_paths: tuple[str, ...] = (),
) -> CubePackRowView:
    """Return a display model for one tracked Cube Pack."""

    badges = _pack_badges(pack)
    can_remove = not pack.default_base_repo
    return CubePackRowView(
        repo_ref=pack.repo_ref,
        owner=pack.owner,
        repo=pack.repo,
        title=pack.repo_ref,
        subtitle=_pack_subtitle(pack),
        badges=badges,
        enabled=pack.enabled,
        can_remove=can_remove,
        remove_disabled_reason="" if can_remove else BASE_PACK_REMOVE_DISABLED_REASON,
        details=_pack_details(pack, cube_paths=cube_paths),
    )


def project_readiness(readiness: object | None) -> CubeLibraryReadinessView:
    """Return a display model for target readiness."""

    if not isinstance(readiness, CubeLibraryReadiness):
        return CubeLibraryReadinessView(
            ready=False,
            title="Target Readiness",
            summary="Readiness unavailable from the active target.",
            details=(),
        )

    missing = readiness.missing_custom_nodes
    version_issues = tuple(
        item
        for item in readiness.dependency_version_plan
        if item.status not in {"satisfied", "missing"}
    )
    runtime_issue = (
        readiness.comfy_runtime
        if readiness.comfy_runtime is not None
        and readiness.comfy_runtime.status not in {"", "satisfied"}
        else None
    )
    summary = (
        "Required custom nodes are installed."
        if not missing and not version_issues and runtime_issue is None
        else f"Missing custom nodes: {len(missing)}"
        if missing
        else f"Dependency version issues: {len(version_issues) + int(runtime_issue is not None)}"
    )
    details = (
        CubePackDetailView(
            label="Required custom nodes",
            value=_join_values(readiness.required_custom_nodes),
        ),
        CubePackDetailView(
            label="Missing custom nodes",
            value=_join_values(missing),
            severity="error" if missing else "success",
        ),
        CubePackDetailView(
            label="Installed custom nodes",
            value=_join_values(readiness.installed_custom_nodes),
            visible=bool(readiness.installed_custom_nodes),
        ),
        CubePackDetailView(
            label="Install support",
            value=_yes_no(readiness.install_supported),
        ),
        CubePackDetailView(label="Can install", value=_yes_no(readiness.can_install)),
        CubePackDetailView(
            label="Readiness errors",
            value=_join_values(readiness.errors),
            severity="error",
            visible=bool(readiness.errors),
        ),
        CubePackDetailView(
            label="Dependency versions",
            value=_version_issue_text(version_issues),
            severity="error",
            visible=bool(version_issues),
        ),
        CubePackDetailView(
            label="Comfy runtime",
            value=_runtime_issue_text(runtime_issue),
            severity="error",
            visible=runtime_issue is not None,
        ),
    )
    return CubeLibraryReadinessView(
        ready=readiness.ready
        and not missing
        and not version_issues
        and runtime_issue is None,
        title="Target Readiness",
        summary=summary,
        details=tuple(detail for detail in details if detail.visible),
    )


def _pack_subtitle(pack: CubePackRecord) -> str:
    """Return the concise collapsed-row status summary for one pack."""

    parts = [_cube_count_text(pack.cube_count), _last_sync_summary(pack)]
    if not pack.enabled:
        parts.append("Disabled")
    if pack.update_available:
        parts.append("Update available")
    return " · ".join(parts)


def _pack_badges(pack: CubePackRecord) -> tuple[CubePackBadgeView, ...]:
    """Return notable compact badges for one pack."""

    badges: list[CubePackBadgeView] = []
    if pack.default_base_repo:
        badges.append(CubePackBadgeView("Base", "neutral"))
    if not pack.enabled:
        badges.append(CubePackBadgeView("Disabled", "warning"))
    if pack.update_available:
        badges.append(CubePackBadgeView("Update available", "warning"))
    if _failed(pack.last_sync_status, pack.last_sync_error):
        badges.append(CubePackBadgeView("Sync failed", "error"))
    return tuple(badges)


def _pack_details(
    pack: CubePackRecord,
    *,
    cube_paths: tuple[str, ...],
) -> tuple[CubePackDetailView, ...]:
    """Return expanded detail rows for one tracked Cube Pack."""

    details = (
        CubePackDetailView("Cubes", _cube_list_text(cube_paths, pack.cube_count)),
        CubePackDetailView("Last synced", _time_or_never(pack.last_sync_at)),
        CubePackDetailView(
            "Sync status",
            _text_or_unknown(pack.last_sync_status),
            _status_severity(pack.last_sync_status, pack.last_sync_error),
            visible=bool(pack.last_sync_status.strip()),
        ),
        CubePackDetailView(
            "Last sync error",
            pack.last_sync_error.strip(),
            "error",
            visible=bool(pack.last_sync_error.strip()),
        ),
        CubePackDetailView(
            "Update",
            "Available",
            "warning",
            visible=pack.update_available,
        ),
    )
    return tuple(detail for detail in details if detail.visible)


def _last_sync_summary(pack: CubePackRecord) -> str:
    """Return the collapsed last-sync summary for one pack."""

    if _failed(pack.last_sync_status, pack.last_sync_error):
        return "Sync failed"
    if pack.last_sync_at.strip():
        return f"Last synced {pack.last_sync_at.strip()}"
    if pack.last_sync_status.strip():
        return f"Sync {_text_or_unknown(pack.last_sync_status)}"
    return "Never synced"


def _status_severity(status: str, error: str) -> BadgeSeverity:
    """Return display severity for one backend status/error pair."""

    if _failed(status, error):
        return "error"
    if status.strip():
        return "success"
    return "neutral"


def _failed(status: str, error: str) -> bool:
    """Return whether one status pair should be treated as failed."""

    normalized = status.strip().lower()
    return bool(error.strip()) or normalized in {"error", "failed", "failure"}


def _cube_count_text(count: int) -> str:
    """Return user-facing cube-count text."""

    noun = "cube" if count == 1 else "cubes"
    return f"{count} {noun}"


def _cube_list_text(cube_paths: tuple[str, ...], fallback_count: int) -> str:
    """Return cube path list text, falling back to a count when unavailable."""

    visible_paths = tuple(path.strip() for path in cube_paths if path.strip())
    return (
        ", ".join(visible_paths) if visible_paths else _cube_count_text(fallback_count)
    )


def _text_or_unknown(value: str) -> str:
    """Return trimmed text or an unknown placeholder."""

    stripped = value.strip()
    return stripped if stripped else "unknown"


def _time_or_never(value: str) -> str:
    """Return trimmed timestamp text or a never placeholder."""

    stripped = value.strip()
    return stripped if stripped else "Never"


def _yes_no(value: bool) -> str:
    """Return a concise yes/no value."""

    return "Yes" if value else "No"


def _join_values(values: tuple[str, ...]) -> str:
    """Return a comma-separated display value for string tuples."""

    visible_values = tuple(value.strip() for value in values if value.strip())
    return ", ".join(visible_values) if visible_values else "None"


def _version_issue_text(values: object) -> str:
    """Return concise display text for dependency version issues."""

    if not isinstance(values, tuple):
        return "None"
    parts = [
        f"{item.display_name}: {item.status}"
        for item in values
        if getattr(item, "display_name", "") and getattr(item, "status", "")
    ]
    return ", ".join(parts) if parts else "None"


def _runtime_issue_text(value: object) -> str:
    """Return concise display text for Comfy runtime readiness."""

    if value is None:
        return "None"
    required = getattr(value, "required_version", "")
    status = getattr(value, "status", "")
    if required:
        return f"Comfy {required}: {status}"
    return str(status or "unknown")


__all__ = [
    "BASE_PACK_REMOVE_DISABLED_REASON",
    "BadgeSeverity",
    "CubeLibraryReadinessView",
    "CubeLibraryStatusView",
    "CubePackBadgeView",
    "CubePackDetailView",
    "CubePackRowView",
    "project_library_status",
    "project_pack",
    "project_readiness",
]
