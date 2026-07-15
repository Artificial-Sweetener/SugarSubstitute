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

"""Tests for managed ComfyUI containment strategy selection."""

from __future__ import annotations

import pytest

from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedContainmentError,
    select_containment_mode,
)


def test_select_containment_mode_uses_windows_job_objects() -> None:
    """Windows platforms should select Job Object containment."""

    assert select_containment_mode(platform="win32") == "windows_job_object"


def test_select_containment_mode_uses_posix_guardian_on_linux() -> None:
    """Linux platforms should select shared POSIX guardian containment."""

    assert select_containment_mode(platform="linux") == "posix_guardian"


def test_select_containment_mode_uses_posix_guardian_on_macos() -> None:
    """macOS should use the same process-group guardian ownership as Linux."""

    assert select_containment_mode(platform="darwin") == "posix_guardian"


def test_select_containment_mode_fails_closed_for_unsupported_platforms() -> None:
    """Unsupported platforms should fail closed with a clear containment diagnostic."""

    with pytest.raises(ManagedContainmentError, match="Windows, Linux, and macOS"):
        select_containment_mode(platform="freebsd")
