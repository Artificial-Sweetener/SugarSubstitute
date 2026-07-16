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

"""Public Comfy nodepack reconciliation facade."""

from __future__ import annotations

from substitute.infrastructure.comfy.core_nodepack_reconciler import (
    ensure_core_comfy_nodepacks as ensure_core_comfy_nodepacks,
    refresh_core_comfy_nodepacks as refresh_core_comfy_nodepacks,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    CORE_COMFY_NODEPACKS as CORE_COMFY_NODEPACKS,
    CoreComfyNodepack as CoreComfyNodepack,
)
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    core_nodepack_installed as core_nodepack_installed,
)
from substitute.infrastructure.comfy.sugarcubes_maintenance_runner import (
    run_sugarcubes_baseline_maintenance as run_sugarcubes_baseline_maintenance,
)


__all__ = [
    "CORE_COMFY_NODEPACKS",
    "CoreComfyNodepack",
    "core_nodepack_installed",
    "ensure_core_comfy_nodepacks",
    "refresh_core_comfy_nodepacks",
    "run_sugarcubes_baseline_maintenance",
]
