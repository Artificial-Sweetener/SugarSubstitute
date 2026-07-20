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

"""Protect exact verified runtime and toolchain dependencies."""

from __future__ import annotations

from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_RUNTIME_DEPENDENCIES = frozenset(
    {
        "comtypes",
        "ijson",
        "keyring",
        "pillow",
        "photoshop",
        "py7zr",
        "pyenchant",
        "pygit2",
        "pyobjc-core",
        "pyobjc-framework-cocoa",
        "psutil",
        "pyside6",
        "pyside6-fluent-widgets",
        "pysidesix-frameless-window",
        "qpane",
        "requests",
        "truststore",
        "websocket-client",
        "winaccent",
    }
)
_EXPECTED_TOOLCHAIN_DEPENDENCIES = frozenset(
    {
        "mypy",
        "pip",
        "pip-audit",
        "pre-commit",
        "pyinstaller",
        "pytest",
        "pytest-xdist",
        "ruff",
        "uv",
    }
)


def test_runtime_requirements_match_verified_versions() -> None:
    """Keep every direct runtime dependency at its verified version."""

    requirements = _read_runtime_requirements()

    assert requirements.keys() == _EXPECTED_RUNTIME_DEPENDENCIES
    for requirement in requirements.values():
        _assert_exact_registry_pin(requirement)


def test_toolchain_requirements_match_verified_versions() -> None:
    """Keep every development and CI tool at its verified version."""

    requirements = _read_requirements("requirements-toolchain.txt")

    assert requirements.keys() == _EXPECTED_TOOLCHAIN_DEPENDENCIES
    for requirement in requirements.values():
        _assert_exact_registry_pin(requirement)


def _assert_exact_registry_pin(requirement: Requirement) -> None:
    """Require one immutable registry version without duplicating its value."""

    specifiers = tuple(requirement.specifier)
    assert requirement.url is None
    assert len(specifiers) == 1
    assert specifiers[0].operator == "=="
    assert specifiers[0].version


def _read_runtime_requirements() -> dict[str, Requirement]:
    """Parse declared requirements while preserving environment-marker entries."""

    return _read_requirements("requirements.txt")


def _read_requirements(filename: str) -> dict[str, Requirement]:
    """Parse direct requirement entries from one repository requirement file."""

    requirements: dict[str, Requirement] = {}
    for raw_line in (
        (_REPOSITORY_ROOT / filename).read_text(encoding="utf-8").splitlines()
    ):
        line = raw_line.split(" #", maxsplit=1)[0].strip()
        if not line or line.startswith(("#", "-r ")):
            continue
        requirement = Requirement(line)
        requirements[canonicalize_name(requirement.name)] = requirement
    return requirements
