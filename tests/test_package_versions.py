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

"""Tests for shared Python distribution version resolution."""

from __future__ import annotations

from importlib import metadata

import pytest

from substitute.domain.runtime_versions import (
    PYSIDE6_DISTRIBUTION_NAMES,
    PYSIDE6_FLUENT_WIDGETS_DISTRIBUTION_NAMES,
)
from substitute.infrastructure.python_packages import installed_distribution_version


def test_installed_distribution_version_returns_first_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Package version resolver should return the first installed candidate."""

    def fake_version(name: str) -> str:
        """Return a version only for the second candidate."""

        if name == "second":
            return "2.0.1"
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", fake_version)

    version = installed_distribution_version(
        ("first", "second"),
        fallback="missing",
    )

    assert version == "2.0.1"


def test_installed_distribution_version_returns_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Package version resolver should degrade to the provided fallback."""

    def fake_version(name: str) -> str:
        """Raise a package-not-found error for every candidate."""

        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", fake_version)

    version = installed_distribution_version(
        ("missing",),
        fallback="source checkout",
    )

    assert version == "source checkout"


def test_pyside_runtime_distribution_names_match_installed_packages() -> None:
    """PySide UI package constants should resolve installed distribution names."""

    assert PYSIDE6_DISTRIBUTION_NAMES == ("PySide6",)
    assert PYSIDE6_FLUENT_WIDGETS_DISTRIBUTION_NAMES == ("PySide6-Fluent-Widgets",)
