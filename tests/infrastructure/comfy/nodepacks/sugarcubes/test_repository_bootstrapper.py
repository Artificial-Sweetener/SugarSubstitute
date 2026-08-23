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

"""Tests for Git-free SugarCubes repository preparation."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.sugarcubes_repository_bootstrapper import (
    BASE_CUBES_REPOSITORY_URL,
    prepare_sugarcubes_repositories,
)
from tests.support.version_control.repository_service_support import (
    RecordingRepositoryService,
)


def test_sugarcubes_repository_preparation_initializes_and_clones(
    tmp_path: Path,
) -> None:
    """Fresh SugarCubes state should be prepared entirely by RepositoryService."""

    repositories = RecordingRepositoryService(
        clone_callback=lambda _url, target: target.mkdir(parents=True)
    )

    prepare_sugarcubes_repositories(tmp_path, repositories=repositories)

    data_root = tmp_path / ".sugarcubes"
    assert repositories.calls == [
        ("initialize", (data_root / "local", "main")),
        (
            "clone",
            (
                BASE_CUBES_REPOSITORY_URL,
                data_root / "Artificial-Sweetener" / "Base-Cubes",
            ),
        ),
    ]


def test_sugarcubes_repository_preparation_fast_forwards_existing_base(
    tmp_path: Path,
) -> None:
    """Recurring setup should synchronize an existing Base-Cubes checkout."""

    data_root = tmp_path / ".sugarcubes"
    (data_root / "local" / ".git").mkdir(parents=True)
    base_root = data_root / "Artificial-Sweetener" / "Base-Cubes"
    (base_root / ".git").mkdir(parents=True)
    repositories = RecordingRepositoryService()

    prepare_sugarcubes_repositories(tmp_path, repositories=repositories)

    assert repositories.calls == [("sync_fast_forward", base_root)]


def test_sugarcubes_repository_preparation_preserves_unsynchronized_local_base(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Local development history must remain usable when sync is not fast-forwardable."""

    data_root = tmp_path / ".sugarcubes"
    (data_root / "local" / ".git").mkdir(parents=True)
    base_root = data_root / "Artificial-Sweetener" / "Base-Cubes"
    (base_root / ".git").mkdir(parents=True)
    repositories = RecordingRepositoryService(failing_operations={"sync_fast_forward"})
    emitted: list[str] = []

    with caplog.at_level(logging.WARNING):
        prepare_sugarcubes_repositories(
            tmp_path,
            repositories=repositories,
            on_log=emitted.append,
        )

    assert repositories.calls == [("sync_fast_forward", base_root)]
    assert base_root.is_dir()
    assert emitted == [
        "WARNING: SugarCubes[base_cubes_sync_skipped]: "
        "Base-Cubes synchronization skipped: The existing local checkout "
        "was preserved and will be used."
    ]
    repository_records = [
        record
        for record in caplog.records
        if record.name.endswith("sugarcubes_repository_bootstrapper")
    ]
    assert len(repository_records) == 1
    assert repository_records[0].levelno == logging.WARNING
    assert repository_records[0].exc_info is None
    assert "Retaining existing Base-Cubes checkout" in repository_records[0].message
