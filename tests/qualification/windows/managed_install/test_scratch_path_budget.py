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

"""Characterize the path budget required by managed-install scratch storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.infrastructure.comfy.managed_install_scratch import (
    MANAGED_INSTALL_PATH_CONTRACT,
    PIP_TEMP_DESCENDANT_BUDGET,
    allocate_managed_install_scratch,
)
from sugarsubstitute_shared.windows_long_paths import WINDOWS_LEGACY_PATH_LIMIT


@pytest.mark.platforms("windows")
def test_default_scratch_preserves_space_for_pip_owned_descendants() -> None:
    """Pip should retain its descendant budget independently of workspace depth."""

    workspace = Path(
        r"E:\Documents\Everything\Artificial Sweetener\runtime\managed-comfy"
    )
    scratch = allocate_managed_install_scratch(workspace)
    try:
        temp_dir = scratch.root / "temp"

        assert MANAGED_INSTALL_PATH_CONTRACT.accepts(scratch.root)
        assert (
            len(str(temp_dir)) + PIP_TEMP_DESCENDANT_BUDGET < WINDOWS_LEGACY_PATH_LIMIT
        )
        assert workspace not in scratch.root.parents
    finally:
        scratch.cleanup()
