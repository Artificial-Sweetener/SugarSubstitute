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

"""Inspect a staged application version without executing staged code."""

from __future__ import annotations

import ast
from pathlib import Path


class RepairPayloadVersionError(RuntimeError):
    """Report absent, ambiguous, or invalid staged version metadata."""


def inspect_app_payload_version(app_dir: Path) -> str:
    """Return the sole literal ``__version__`` assignment in the payload."""

    version_path = app_dir / "substitute" / "_version.py"
    try:
        module = ast.parse(version_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError) as error:
        raise RepairPayloadVersionError(
            f"Repair payload version metadata is unreadable: {version_path}"
        ) from error
    versions: list[str] = []
    for statement in module.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        value = statement.value
        if any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in targets
        ):
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                raise RepairPayloadVersionError(
                    "Repair payload version must be a literal string."
                )
            versions.append(value.value)
    if len(versions) != 1 or not versions[0]:
        raise RepairPayloadVersionError(
            "Repair payload must declare one non-empty __version__."
        )
    return versions[0]


__all__ = ["RepairPayloadVersionError", "inspect_app_payload_version"]
