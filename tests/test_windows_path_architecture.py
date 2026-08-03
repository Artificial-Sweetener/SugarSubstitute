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

"""Enforce ownership boundaries for Windows path compatibility."""

from __future__ import annotations

import ast
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_ENVIRONMENT_OWNER = Path(
    "substitute/infrastructure/comfy/managed_install_environment.py"
)
_PATH_ENVIRONMENT_KEYS = {"TEMP", "TMP", "TMPDIR", "PIP_CACHE_DIR"}


def test_managed_temporary_environment_has_one_source_owner() -> None:
    """Installer code should not reconstruct path-bearing environment variables."""

    assignments: set[tuple[Path, str]] = set()
    for source_path in _production_python_files():
        relative_path = source_path.relative_to(_REPOSITORY_ROOT)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                key = _string_subscript_key(target)
                if key in _PATH_ENVIRONMENT_KEYS:
                    assignments.add((relative_path, key))

    assert assignments == {
        (_ENVIRONMENT_OWNER, "TEMP"),
        (_ENVIRONMENT_OWNER, "TMP"),
        (_ENVIRONMENT_OWNER, "TMPDIR"),
        (_ENVIRONMENT_OWNER, "PIP_CACHE_DIR"),
    }


def test_orchestrators_do_not_construct_external_scratch_paths() -> None:
    """Application and launch orchestration should delegate scratch placement."""

    orchestrators = (
        Path("substitute/application/onboarding/flow_service.py"),
        Path("substitute/infrastructure/comfy/managed_install.py"),
        Path("substitute/infrastructure/comfy/managed_launcher.py"),
    )

    for relative_path in orchestrators:
        source = (_REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "installer-temp" not in source
        assert ".substitute-installer-temp" not in source


def test_path_representation_does_not_own_external_failure_diagnosis() -> None:
    """Path transport and external diagnostics should remain separate concerns."""

    source = (
        _REPOSITORY_ROOT / "sugarsubstitute_shared/windows_long_paths.py"
    ).read_text(encoding="utf-8")

    assert "ExternalLongPathCompatibilityError" not in source
    assert "external_long_path_error" not in source


def test_repository_clone_delegates_external_scratch_placement() -> None:
    """Repository subprocess orchestration should not invent temporary roots."""

    source = (
        _REPOSITORY_ROOT / "substitute/infrastructure/version_control/clone_process.py"
    ).read_text(encoding="utf-8")

    assert "RepositoryPathWorkspace.reserve" in source
    assert "tempfile" not in source


def _production_python_files() -> tuple[Path, ...]:
    """Return first-party runtime Python files covered by the ownership gate."""

    roots = ("launcher", "substitute", "sugarsubstitute_shared")
    return tuple(
        source_path
        for root in roots
        for source_path in (_REPOSITORY_ROOT / root).rglob("*.py")
    )


def _string_subscript_key(node: ast.AST) -> str | None:
    """Return a literal string key assigned through one subscript."""

    if not isinstance(node, ast.Subscript):
        return None
    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        return node.slice.value
    return None
