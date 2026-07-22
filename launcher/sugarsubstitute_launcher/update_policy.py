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

"""Decide launcher update checks and app payload installs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from launcher.sugarsubstitute_launcher.config import LauncherConfig


class UpdateCheckDecision(Enum):
    """Identify whether the launcher should load a release manifest."""

    SKIP = "skip"
    CHECK = "check"


class AppPayloadUpdateDecision(Enum):
    """Identify whether the launcher should install a manifest payload."""

    SKIP = "skip"
    INSTALL = "install"


@dataclass(frozen=True, slots=True)
class UpdateCheckPolicyResult:
    """Describe the update-check policy outcome."""

    decision: UpdateCheckDecision
    reason: str


@dataclass(frozen=True, slots=True)
class AppPayloadUpdatePolicyResult:
    """Describe the app-payload update policy outcome."""

    decision: AppPayloadUpdateDecision
    reason: str


def decide_update_check(
    *,
    config: LauncherConfig,
    no_update_check: bool,
) -> UpdateCheckPolicyResult:
    """Return whether launcher startup should check the release manifest."""

    if no_update_check:
        return UpdateCheckPolicyResult(UpdateCheckDecision.SKIP, "cli_disabled")
    if not config.update_check.enabled:
        return UpdateCheckPolicyResult(UpdateCheckDecision.SKIP, "config_disabled")
    frequency = config.update_check.frequency.lower()
    if frequency == "manual":
        return UpdateCheckPolicyResult(UpdateCheckDecision.SKIP, "manual")
    return UpdateCheckPolicyResult(UpdateCheckDecision.CHECK, "startup")


def decide_app_payload_update(
    *,
    installed_version: str | None,
    manifest_version: str,
) -> AppPayloadUpdatePolicyResult:
    """Return whether the manifest app payload should be installed."""

    if installed_version is None:
        return AppPayloadUpdatePolicyResult(
            AppPayloadUpdateDecision.INSTALL,
            "missing_installed_version",
        )
    comparison = compare_release_versions(manifest_version, installed_version)
    if comparison > 0:
        return AppPayloadUpdatePolicyResult(
            AppPayloadUpdateDecision.INSTALL,
            "manifest_newer",
        )
    return AppPayloadUpdatePolicyResult(
        AppPayloadUpdateDecision.SKIP,
        "installed_current",
    )


def compare_release_versions(left: str, right: str) -> int:
    """Compare simple release version strings without accepting path-like values."""

    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    maximum_length = max(len(left_parts), len(right_parts))
    padded_left = [*left_parts, *([0] * (maximum_length - len(left_parts)))]
    padded_right = [*right_parts, *([0] * (maximum_length - len(right_parts)))]
    if padded_left > padded_right:
        return 1
    if padded_left < padded_right:
        return -1
    return 0


def _version_parts(version: str) -> list[int]:
    """Parse one dotted numeric release version."""

    normalized = version.removeprefix("v").strip()
    if not normalized:
        raise ValueError("Release version must not be empty.")
    if any(character in normalized for character in ("/", "\\", ":")):
        raise ValueError(f"Release version must be a plain tag value: {version}")
    parts: list[int] = []
    for raw_part in normalized.split("."):
        if not raw_part.isdigit():
            raise ValueError(f"Release version must be dotted numeric: {version}")
        parts.append(int(raw_part))
    return parts
