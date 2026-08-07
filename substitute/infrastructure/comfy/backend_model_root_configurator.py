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

"""Invoke BackEnd's offline configurator during first-time Comfy provisioning."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    resolve_installed_nodepack_root,
)
from substitute.infrastructure.process.hidden_process_runner import run_command

_CONFIGURATOR = "configure_model_root.py"


def configure_backend_model_root(
    *,
    workspace: Path,
    python_executable: Path,
    model_root: Path | None,
) -> None:
    """Ask the installed BackEnd to persist an offline model-root selection."""

    backend = next(
        item
        for item in CORE_COMFY_NODEPACKS
        if item.nodepack_id is CoreNodepackId.SUBSTITUTE_BACKEND
    )
    backend_root = resolve_installed_nodepack_root(workspace, backend)
    configurator = backend_root / _CONFIGURATOR
    if not configurator.is_file():
        raise RuntimeError(
            "Installed Substitute BackEnd does not support model-root configuration."
        )
    selection = ["--default"] if model_root is None else ["--path", str(model_root)]
    run_command(
        (
            str(python_executable),
            str(configurator),
            "--comfy-root",
            str(workspace),
            *selection,
        ),
        cwd=backend_root,
        check=True,
    )


__all__ = ["configure_backend_model_root"]
