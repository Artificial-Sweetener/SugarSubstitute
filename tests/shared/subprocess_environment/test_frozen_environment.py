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

"""Verify external children shed bootloader state across unfrozen helpers."""

from __future__ import annotations

import sys

import pytest

from sugarsubstitute_shared.subprocess_environment import (
    clean_frozen_parent_environment,
)


@pytest.mark.parametrize("support_path", [None, ""])
def test_unfrozen_helper_discards_inherited_bootloader_state(
    monkeypatch: pytest.MonkeyPatch, support_path: str | None
) -> None:
    """A runtime-Python migration helper must launch a fresh onefile instance."""
    if support_path is None:
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    else:
        monkeypatch.setattr(sys, "_MEIPASS", support_path, raising=False)
    inherited = {
        "_PYI_ARCHIVE_FILE": "SugarSubstitute.exe",
        "_PYI_APPLICATION_HOME_DIR": "retired-extraction",
        "_PYI_PARENT_PROCESS_LEVEL": "1",
        "_PYI_SPLASH_IPC": "retired-splash",
        "PATH": "ordinary-path",
        "PYTHONPATH": "application-source",
        "PYINSTALLER_SUPPRESS_SPLASH_SCREEN": "1",
        "QUALIFICATION_TOKEN": "preserved",
    }
    original = dict(inherited)

    environment = clean_frozen_parent_environment(inherited)

    assert environment == {
        "PATH": "ordinary-path",
        "PYTHONPATH": "application-source",
        "PYINSTALLER_SUPPRESS_SPLASH_SCREEN": "1",
        "QUALIFICATION_TOKEN": "preserved",
    }
    assert inherited == original
    assert clean_frozen_parent_environment(environment) == environment
