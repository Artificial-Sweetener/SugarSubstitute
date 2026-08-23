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

"""Verify managed workspace repository service operations."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
from substitute.infrastructure.comfy import managed_workspace_operations
from tests.support.version_control.repository_service_support import (
    RecordingRepositoryService,
)


def test_clone_managed_workspace_uses_self_contained_repository_service(
    tmp_path: Path,
) -> None:
    """Managed Comfy cloning should not route through process execution."""

    repositories = RecordingRepositoryService()

    managed_workspace_operations.clone_managed_workspace(
        tmp_path, repositories=repositories
    )

    assert repositories.calls == [
        (
            "clone",
            ("https://github.com/comfyanonymous/ComfyUI.git", tmp_path),
        )
    ]


def test_sync_managed_workspace_uses_self_contained_fast_forward(
    tmp_path: Path,
) -> None:
    """Managed Comfy updates should delegate one fail-closed fast-forward."""

    (tmp_path / ".git").mkdir(parents=True)
    repositories = RecordingRepositoryService()

    managed_workspace_operations.sync_managed_workspace_repository(
        tmp_path,
        repositories=repositories,
    )

    assert repositories.calls == [("sync_fast_forward", tmp_path)]
