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

"""Test Python runtime policy failure handling."""

from __future__ import annotations

import subprocess

import pytest

from substitute.infrastructure.comfy import python_policy


def test_python_probe_treats_timeout_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permit policy fallback when an optional interpreter probe stalls."""

    def time_out(*_args: object, **_kwargs: object) -> object:
        """Simulate a Python launcher that does not answer promptly."""

        raise subprocess.TimeoutExpired(["py", "-3.13"], timeout=5)

    monkeypatch.setattr(subprocess, "run", time_out)

    assert python_policy._resolve_windows_py_launcher("3.13") is None
