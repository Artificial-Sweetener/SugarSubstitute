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

"""Protect verified compatibility windows for runtime dependencies."""

from __future__ import annotations

from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_SPECIFIERS = {
    "comtypes": frozenset({(">=", "1.4.16"), ("<", "2.0.0")}),
    "keyring": frozenset({(">=", "25.7.0"), ("<", "26.0.0")}),
    "pillow": frozenset({(">=", "12.3.0"), ("<", "13.0.0")}),
    "photoshop": frozenset({(">=", "0.21.9"), ("<", "0.22.0")}),
    "py7zr": frozenset({("==", "1.1.3")}),
    "pyenchant": frozenset({(">=", "3.3.0"), ("<", "4.0.0")}),
    "pygit2": frozenset({("==", "1.19.3")}),
    "pyobjc-core": frozenset({(">=", "12.2.1"), ("<", "13.0.0")}),
    "pyobjc-framework-cocoa": frozenset({(">=", "12.2.1"), ("<", "13.0.0")}),
    "psutil": frozenset({(">=", "7.2.2"), ("<", "8.0.0")}),
    "pyside6": frozenset({(">=", "6.11.1"), ("<", "6.12.0")}),
    "pyside6-fluent-widgets": frozenset({(">=", "1.11.2"), ("<", "2.0.0")}),
    "pysidesix-frameless-window": frozenset({(">=", "0.8.1"), ("<", "1.0.0")}),
    "qpane": frozenset({(">=", "2.0.4"), ("<", "3.0.0")}),
    "requests": frozenset({(">=", "2.34.2"), ("<", "3.0.0")}),
    "websocket-client": frozenset({(">=", "1.9.0"), ("<", "2.0.0")}),
    "winaccent": frozenset({(">=", "2.1.0"), ("<", "3.0.0")}),
}


def test_runtime_requirements_match_native_ci_compatibility_windows() -> None:
    """Keep every declared runtime dependency inside its verified version window."""

    requirements = _read_runtime_requirements()

    assert requirements.keys() == _EXPECTED_SPECIFIERS.keys()
    for name, requirement in requirements.items():
        actual = frozenset(
            (specifier.operator, specifier.version)
            for specifier in requirement.specifier
        )
        assert actual == _EXPECTED_SPECIFIERS[name]


def _read_runtime_requirements() -> dict[str, Requirement]:
    """Parse declared requirements while preserving environment-marker entries."""

    requirements: dict[str, Requirement] = {}
    for raw_line in (
        (_REPOSITORY_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    ):
        line = raw_line.split(" #", maxsplit=1)[0].strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        requirements[canonicalize_name(requirement.name)] = requirement
    return requirements
