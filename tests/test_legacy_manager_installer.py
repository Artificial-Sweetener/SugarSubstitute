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

"""Verify legacy Manager installation ownership in isolation."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.infrastructure.comfy.legacy_manager_installer import (
    LegacyComfyManagerInstaller,
)
from substitute.infrastructure.comfy.manager_contract import ComfyManagerContract
from tests.repository_service_test_double import RecordingRepositoryService


def test_legacy_installer_preserves_existing_user_checkout(tmp_path: Path) -> None:
    """Reject replacement when a legacy Manager directory already exists."""

    contract = ComfyManagerContract(tmp_path)
    contract.legacy_directory.mkdir(parents=True)
    repositories = RecordingRepositoryService()

    with pytest.raises(RuntimeError, match="left unchanged"):
        LegacyComfyManagerInstaller(repositories=repositories).install(
            contract=contract,
            python_executable=tmp_path / "python",
            repository_url="https://example.invalid/manager.git",
            previous_failure="broken checkout",
        )

    assert repositories.calls == []
