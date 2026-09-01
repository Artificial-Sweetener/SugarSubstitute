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

"""Load persisted Comfy ownership evidence without importing the application runtime."""

from __future__ import annotations

import json

from launcher.sugarsubstitute_launcher.application.repair.models import (
    ManagedComfyOwnership,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.windows_long_paths import operational_path


class RepairOwnershipError(RuntimeError):
    """Report unreadable or structurally invalid persisted ownership evidence."""


def load_comfy_ownership(layout: InstallLayout) -> ManagedComfyOwnership | None:
    """Load configured Comfy ownership facts while preserving missing configuration."""

    current_path = layout.user_dir / "settings" / "comfy_target.json"
    legacy_path = layout.root / "config" / "comfy_target.json"
    path = current_path if current_path.exists() else legacy_path
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RepairOwnershipError(
            f"Comfy ownership configuration is unreadable: {path}"
        ) from error
    if not isinstance(payload, dict):
        raise RepairOwnershipError(
            f"Comfy ownership configuration must be an object: {path}"
        )
    mode = payload.get("mode")
    workspace_value = payload.get("workspace_path")
    install_owned = payload.get("install_owned")
    if (
        not isinstance(mode, str)
        or (workspace_value is not None and not isinstance(workspace_value, str))
        or not isinstance(install_owned, bool)
    ):
        raise RepairOwnershipError(
            f"Comfy ownership configuration has invalid fields: {path}"
        )
    return ManagedComfyOwnership(
        target_mode=mode,
        workspace_root=(
            operational_path(workspace_value)
            if isinstance(workspace_value, str)
            else None
        ),
        install_owned=install_owned,
    )


__all__ = ["RepairOwnershipError", "load_comfy_ownership"]
