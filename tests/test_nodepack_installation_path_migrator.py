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

"""Tests for persisted nodepack path canonicalization."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.comfy.nodepack_installation_path_migrator import (
    canonicalize_nodepack_root,
)
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    resolve_installed_nodepack_root,
)


def test_legacy_folder_is_atomically_canonicalized_with_all_data(
    tmp_path: Path,
) -> None:
    """Give Manager its Registry path without rebuilding or dropping the folder."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    legacy_root = tmp_path / nodepack.legacy_folders[0]
    legacy_root.mkdir(parents=True)
    (legacy_root / ".tracking").write_text("pyproject.toml", encoding="utf-8")
    cache_file = legacy_root / "cache" / "user.json"
    cache_file.parent.mkdir()
    cache_file.write_text("preserve", encoding="utf-8")
    observed_root = resolve_installed_nodepack_root(tmp_path, nodepack)

    canonical_root = canonicalize_nodepack_root(
        workspace=tmp_path,
        current_root=observed_root,
        nodepack=nodepack,
        on_log=None,
    )

    actual_names = {child.name for child in canonical_root.parent.iterdir()}
    assert canonical_root.name in actual_names
    assert nodepack.legacy_folders[0].name not in actual_names
    assert (canonical_root / "cache" / "user.json").read_text(
        encoding="utf-8"
    ) == "preserve"
    assert (canonical_root / ".tracking").is_file()


def test_canonical_folder_is_an_idempotent_noop(tmp_path: Path) -> None:
    """Avoid filesystem churn after migration has settled."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    canonical_root = tmp_path / nodepack.expected_folder
    canonical_root.mkdir(parents=True)

    assert (
        canonicalize_nodepack_root(
            workspace=tmp_path,
            current_root=canonical_root,
            nodepack=nodepack,
            on_log=None,
        )
        == canonical_root
    )
