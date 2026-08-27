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

"""Verify Manager provisioning relies on the shared Python resolver."""

from __future__ import annotations

from pathlib import Path


def test_manager_provisioner_has_no_private_python_resolver() -> None:
    """Keep workspace-Python candidate policy in its shared resolver owner."""

    source = (
        Path(__file__).resolve().parents[4]
        / "substitute"
        / "infrastructure"
        / "comfy"
        / "manager_provisioner.py"
    ).read_text(encoding="utf-8")

    assert "def _resolve_workspace_python" not in source
