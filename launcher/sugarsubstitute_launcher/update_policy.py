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
from sugarsubstitute_shared.launcher_update.versions import compare_release_versions


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
