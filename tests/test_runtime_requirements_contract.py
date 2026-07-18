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
_EXPECTED_SPECIFIERS = {
    "comtypes": frozenset({("==", "1.4.16")}),
    "keyring": frozenset({("==", "25.7.0")}),
    "pillow": frozenset({("==", "12.3.0")}),
    "photoshop": frozenset({("==", "0.21.9")}),
    "py7zr": frozenset({("==", "1.1.3")}),
    "pyenchant": frozenset({("==", "3.3.0")}),
    "pygit2": frozenset({("==", "1.19.3")}),
    "pyobjc-core": frozenset({("==", "12.2.1")}),
    "pyobjc-framework-cocoa": frozenset({("==", "12.2.1")}),
    "psutil": frozenset({("==", "7.2.2")}),
    "pyside6": frozenset({("==", "6.11.1")}),
    "pyside6-fluent-widgets": frozenset({("==", "1.11.2")}),
    "pysidesix-frameless-window": frozenset({("==", "0.8.1")}),
    "qpane": frozenset({("==", "2.1.1")}),
    "requests": frozenset({("==", "2.34.2")}),
    "truststore": frozenset({("==", "0.10.4")}),
    "websocket-client": frozenset({("==", "1.9.0")}),
    "winaccent": frozenset({("==", "2.1.0")}),
}
_EXPECTED_TOOLCHAIN_SPECIFIERS = {
    "mypy": frozenset({("==", "2.3.0")}),
    "pip": frozenset({("==", "26.1.2")}),
    "pip-audit": frozenset({("==", "2.10.1")}),
    "pre-commit": frozenset({("==", "4.6.0")}),
    "pyinstaller": frozenset({("==", "6.21.0")}),
    "pytest": frozenset({("==", "9.1.1")}),
    "pytest-xdist": frozenset({("==", "3.8.0")}),
    "ruff": frozenset({("==", "0.15.22")}),
    "uv": frozenset({("==", "0.11.18")}),
}


def test_runtime_requirements_match_verified_versions() -> None:
    """Keep every direct runtime dependency at its verified version."""

    requirements = _read_runtime_requirements()

    assert requirements.keys() == _EXPECTED_SPECIFIERS.keys()
    for name, requirement in requirements.items():
        actual = frozenset(
            (specifier.operator, specifier.version)
            for specifier in requirement.specifier
        )
        assert actual == _EXPECTED_SPECIFIERS[name]


def test_toolchain_requirements_match_verified_versions() -> None:
    """Keep every development and CI tool at its verified version."""

    requirements = _read_requirements("requirements-toolchain.txt")

    assert requirements.keys() == _EXPECTED_TOOLCHAIN_SPECIFIERS.keys()
    for name, requirement in requirements.items():
        actual = frozenset(
            (specifier.operator, specifier.version)
            for specifier in requirement.specifier
        )
        assert actual == _EXPECTED_TOOLCHAIN_SPECIFIERS[name]


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
