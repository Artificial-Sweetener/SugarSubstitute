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

"""Tests for immutable contracts captured from a ComfyUI checkout."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.domain.comfy_compatibility import UnsupportedComfyVersionError
from substitute.infrastructure.comfy.comfy_checkout_contract import (
    ComfyCheckoutContract,
)


def test_checkout_contract_captures_version_and_content_digests(tmp_path: Path) -> None:
    """Contract evidence should change only when authoritative content changes."""

    _write_contract(tmp_path, version="0.15.0", requirement="numpy>=1.25")
    contract = ComfyCheckoutContract(tmp_path)

    original = contract.capture()
    (tmp_path / "requirements.txt").touch()
    touched = contract.capture()
    (tmp_path / "requirements.txt").write_text("numpy>=2", encoding="utf-8")
    changed = contract.capture()

    assert original.version == "0.15.0"
    assert touched == original
    assert changed.comfy_requirements_digest != original.comfy_requirements_digest
    assert changed.manager_requirements_digest == original.manager_requirements_digest


def test_checkout_contract_rejects_versions_below_support_floor(tmp_path: Path) -> None:
    """Unsupported checkout versions should fail before dependency mutation."""

    _write_contract(tmp_path, version="0.14.2", requirement="numpy")

    with pytest.raises(UnsupportedComfyVersionError, match=r"0\.15\.0.*0\.14\.2"):
        ComfyCheckoutContract(tmp_path).capture()


def test_checkout_contract_rejects_ambiguous_version_source(tmp_path: Path) -> None:
    """Version parsing should fail closed instead of executing checkout code."""

    _write_contract(tmp_path, version="0.15.0", requirement="numpy")
    (tmp_path / "comfyui_version.py").write_text(
        "__version__ = resolve_version()\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="literal __version__"):
        ComfyCheckoutContract(tmp_path).capture()


def _write_contract(workspace: Path, *, version: str, requirement: str) -> None:
    """Write the authoritative files used by one checkout contract fixture."""

    (workspace / "comfyui_version.py").write_text(
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )
    (workspace / "requirements.txt").write_text(requirement, encoding="utf-8")
    (workspace / "manager_requirements.txt").write_text(
        "comfyui_manager==4.1b1\n",
        encoding="utf-8",
    )
