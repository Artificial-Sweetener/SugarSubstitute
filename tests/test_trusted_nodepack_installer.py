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

"""Tests for libgit2-backed trusted nodepack installation."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.infrastructure.comfy.trusted_nodepack_installer import (
    install_trusted_nodepack_repository,
)
from substitute.infrastructure.version_control import RepositoryOperationError
from tests.repository_service_test_double import RecordingRepositoryService


def test_trusted_nodepack_install_removes_partial_failed_clone(tmp_path: Path) -> None:
    """A failed repository operation should not leave a misleading install folder."""

    target = tmp_path / "custom_nodes" / "Example"

    class PartialCloneRepository(RecordingRepositoryService):
        """Fail only after materializing a partial clone fixture."""

        def clone(
            self, repository_url: str, target_path: Path, **kwargs: object
        ) -> None:
            """Create partial output before raising the repository boundary error."""

            _ = repository_url, kwargs
            target_path.mkdir(parents=True)
            (target_path / "partial.txt").write_text("partial", encoding="utf-8")
            raise RepositoryOperationError("forced partial clone")

    repositories = PartialCloneRepository()

    with pytest.raises(RuntimeError, match="trusted Example repository"):
        install_trusted_nodepack_repository(
            repository_url="https://example.invalid/Example.git",
            target_path=target,
            display_name="Example",
            repositories=repositories,
        )

    assert not target.exists()


def test_trusted_nodepack_install_refuses_existing_target(tmp_path: Path) -> None:
    """Existing user data should never be overwritten by a trusted clone."""

    target = tmp_path / "custom_nodes" / "Example"
    target.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="target already exists"):
        install_trusted_nodepack_repository(
            repository_url="https://example.invalid/Example.git",
            target_path=target,
            display_name="Example",
            repositories=RecordingRepositoryService(),
        )
