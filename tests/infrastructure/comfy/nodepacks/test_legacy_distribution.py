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

"""Tests for evidence-based legacy nodepack distribution cleanup."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

import pytest

from substitute.infrastructure.comfy.legacy_nodepack_distribution import (
    LegacyNodepackDistributionCleaner,
)


def test_matching_pep610_origin_is_uninstalled_and_local_metadata_removed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Remove the obsolete pip copy only when its origin proves ownership."""

    egg_info = tmp_path / "substitute_backend.egg-info"
    egg_info.mkdir()
    (egg_info / "PKG-INFO").write_text(
        "Name: substitute-backend\n",
        encoding="utf-8",
    )
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.legacy_nodepack_distribution.run_command",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout=f"{tmp_path.resolve().as_uri()}\n",
            stderr="",
        ),
    )

    def fake_stream(command: list[str], **kwargs: Any) -> tuple[int, tuple[str, ...]]:
        """Record the narrowly authorized pip uninstall."""

        _ = kwargs
        commands.append(command)
        return 0, ()

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.legacy_nodepack_distribution.stream_command_collecting_output",
        fake_stream,
    )

    removed = LegacyNodepackDistributionCleaner().remove_if_owned(
        python_executable=tmp_path / "python.exe",
        nodepack_root=tmp_path,
        distribution_name="substitute-backend",
        on_log=None,
        env=None,
    )

    assert removed is True
    assert commands[0][-3:] == ["uninstall", "--yes", "substitute-backend"]
    assert not egg_info.exists()


def test_unrelated_distribution_origin_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Never uninstall a distribution without exact local-origin evidence."""

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.legacy_nodepack_distribution.run_command",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout="file:///different/source\n",
            stderr="",
        ),
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.legacy_nodepack_distribution.stream_command_collecting_output",
        lambda *args, **kwargs: pytest.fail("pip uninstall must not run"),
    )

    assert not LegacyNodepackDistributionCleaner().remove_if_owned(
        python_executable=tmp_path / "python.exe",
        nodepack_root=tmp_path,
        distribution_name="substitute-backend",
        on_log=None,
        env=None,
    )
