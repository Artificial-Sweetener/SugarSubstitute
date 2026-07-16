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

"""Enumerate bounded Python runtime paths owned by local Comfy layouts."""

from __future__ import annotations

import os
from pathlib import Path

from substitute.domain.onboarding import ComfyPythonCandidate


def attached_comfy_python_candidates(
    workspace: Path,
    *,
    environment: dict[str, str] | None = None,
    platform_name: str | None = None,
) -> tuple[ComfyPythonCandidate, ...]:
    """Return candidates for common source, virtualenv, and portable layouts."""

    resolved_workspace = workspace.resolve()
    parent = resolved_workspace.parent
    active_platform = platform_name or os.name
    entries: list[ComfyPythonCandidate] = []

    def add(root: Path, relative: Path, evidence: str, priority: int) -> None:
        """Append one deterministic candidate."""

        entries.append(ComfyPythonCandidate(root / relative, evidence, priority))

    if active_platform == "nt":
        scripts_python = Path("Scripts/python.exe")
        add(resolved_workspace, Path(".venv") / scripts_python, "workspace .venv", 10)
        add(resolved_workspace, Path("venv") / scripts_python, "workspace venv", 20)
        for spelling in ("python_embeded", "python_embedded"):
            add(resolved_workspace, Path(spelling) / "python.exe", spelling, 30)
            add(parent, Path(spelling) / "python.exe", f"sibling {spelling}", 30)
    else:
        bin_python = Path("bin/python")
        add(resolved_workspace, Path(".venv") / bin_python, "workspace .venv", 10)
        add(resolved_workspace, Path("venv") / bin_python, "workspace venv", 20)
        add(parent, Path(".venv") / bin_python, "parent .venv", 40)
        add(parent, Path("venv") / bin_python, "parent venv", 40)

    active_environment = environment if environment is not None else dict(os.environ)
    for variable in ("VIRTUAL_ENV", "CONDA_PREFIX"):
        value = active_environment.get(variable, "").strip()
        if not value:
            continue
        prefix = Path(value).resolve()
        if not _is_within(prefix, resolved_workspace) and prefix.parent != parent:
            continue
        relative = (
            Path("Scripts/python.exe")
            if active_platform == "nt"
            else Path("bin/python")
        )
        add(prefix, relative, variable, 50)

    deduplicated: dict[str, ComfyPythonCandidate] = {}
    for candidate in entries:
        key = os.path.normcase(str(candidate.executable.resolve()))
        existing = deduplicated.get(key)
        if existing is None or candidate.priority < existing.priority:
            deduplicated[key] = candidate
    return tuple(deduplicated.values())


def resolve_workspace_python(workspace: Path) -> Path:
    """Return the first existing Python path in the established layout order."""

    for candidate in attached_comfy_python_candidates(workspace):
        if candidate.executable.exists():
            return candidate.executable
    raise RuntimeError(
        "Could not find a Python runtime inside the selected ComfyUI workspace."
    )


def _is_within(path: Path, parent: Path) -> bool:
    """Return whether a candidate is inside a bounded discovery root."""

    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


__all__ = ["attached_comfy_python_candidates", "resolve_workspace_python"]
