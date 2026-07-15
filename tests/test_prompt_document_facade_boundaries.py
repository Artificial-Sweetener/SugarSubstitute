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

"""Architecture guards for prompt document facade dependencies."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_PROJECTION_ONLY_MODULES = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_wildcard_diagnostic_provider.py",
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_duplicate_segment_diagnostic_provider.py",
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_spellcheck_candidates.py",
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_scheduled_lora_service.py",
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "effective_scheduled_lora_provider.py",
)
_FOCUSED_COLLABORATOR_MODULES = _PROJECTION_ONLY_MODULES + (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_mutation_service.py",
)


def test_focused_prompt_owners_do_not_import_document_facade() -> None:
    """Focused application owners should avoid the aggregate document facade."""

    offenders = tuple(
        module_path.relative_to(PROJECT_ROOT).as_posix()
        for module_path in _FOCUSED_COLLABORATOR_MODULES
        if _imports_prompt_document_service(module_path)
    )

    assert offenders == ()


def _imports_prompt_document_service(module_path: Path) -> bool:
    """Return whether a module imports the aggregate prompt document facade."""

    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.endswith("prompt_document_service"):
                return True
    return False
