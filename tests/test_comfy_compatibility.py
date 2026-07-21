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

"""Tests for the installer-owned ComfyUI compatibility policy."""

from __future__ import annotations

import pytest

from substitute.domain.comfy_compatibility import (
    COMFY_COMPATIBILITY_POLICY,
    UnsupportedComfyVersionError,
    UnsupportedComfyPythonError,
)


def test_comfyui_support_floor_is_explicitly_0_15_0() -> None:
    """Installer compatibility should have one authoritative public floor."""

    assert COMFY_COMPATIBILITY_POLICY.minimum_comfyui_label == "0.15.0"


@pytest.mark.parametrize(
    ("version", "supported"),
    (("0.14.2", False), ("0.15.0", True), ("v0.24.0", True), ("0.28.2", True)),
)
def test_comfyui_version_floor(version: str, supported: bool) -> None:
    """ComfyUI 0.15.0 should be the exact checkout compatibility boundary."""

    assert COMFY_COMPATIBILITY_POLICY.supports_comfyui(version) is supported


def test_unsupported_comfyui_error_reports_required_and_actual_versions() -> None:
    """Checkout preflight should identify an unsupported ComfyUI version."""

    with pytest.raises(UnsupportedComfyVersionError, match=r"0\.15\.0.*0\.14\.2"):
        COMFY_COMPATIBILITY_POLICY.require_supported_comfyui("0.14.2")


@pytest.mark.parametrize(
    ("version", "supported"),
    (("3.11.9", False), ("3.12.0", True), ("3.13.4", True)),
)
def test_mandatory_nodepack_python_floor(version: str, supported: bool) -> None:
    """Python 3.12 should be the exact attached-runtime boundary."""

    assert COMFY_COMPATIBILITY_POLICY.supports_python(version) is supported


def test_unsupported_python_error_reports_required_and_actual_versions() -> None:
    """Attached preflight should provide actionable version evidence."""

    with pytest.raises(UnsupportedComfyPythonError, match=r"3\.12.*3\.11\.9"):
        COMFY_COMPATIBILITY_POLICY.require_supported_python("3.11.9")
