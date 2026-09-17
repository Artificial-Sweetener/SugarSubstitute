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

"""Admit launcher generations only when they support retained native ownership."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sugarsubstitute_shared.launcher_update.targets import LauncherBundleTarget

_LOGGER = logging.getLogger(__name__)
CONTRACT_FILENAME = "launcher-contract.json"
SUPPORTED_DELEGATION_PROTOCOL = 1


def supports_launcher_delegation(root: Path, target: LauncherBundleTarget) -> bool:
    """Read the sealed producer contract without executing incompatible code.

    This is immutable package metadata, not cached or authoritative user state.
    Older bundles remain valid standalone installations; delegation requires an
    explicit protocol declaration because electing another owner would deadlock.
    """
    path = root / target.support_relative_path / "launcher_assets" / CONTRACT_FILENAME
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        _LOGGER.warning(
            "Launcher delegation contract unavailable | bundle=%s | reason=%s",
            root,
            error,
        )
        return False
    compatible = (
        isinstance(contract, dict)
        and type(contract.get("schema_version")) is int
        and contract["schema_version"] == 1
        and type(contract.get("delegation_protocol")) is int
        and contract["delegation_protocol"] == SUPPORTED_DELEGATION_PROTOCOL
    )
    if not compatible:
        _LOGGER.warning("Launcher delegation contract unsupported | bundle=%s", root)
    return compatible
