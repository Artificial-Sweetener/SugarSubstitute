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

"""Test external scratch allocation and ownership boundaries."""

from __future__ import annotations

from pathlib import Path
import stat

import pytest

from sugarsubstitute_shared import external_scratch
from sugarsubstitute_shared.external_path_contract import ExternalPathContract


def test_allocator_falls_back_when_preferred_parent_is_unusable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An unavailable same-volume root should fall back to user temporary storage."""

    blocked_parent = tmp_path / "blocked"
    blocked_parent.write_text("not a directory", encoding="utf-8")
    fallback_parent = tmp_path / "fallback"
    monkeypatch.setattr(
        external_scratch,
        "_candidate_parents",
        lambda _preferred: (blocked_parent, fallback_parent),
    )

    scratch = external_scratch.allocate_external_scratch(
        preferred_storage_path=tmp_path / "installation",
        namespace="managed-comfy",
        contract=ExternalPathContract(
            component="test component",
            reserved_descendant_length=10,
        ),
    )
    try:
        assert scratch.root.parent == fallback_parent
        assert (scratch.root / ".sugarsubstitute-scratch").is_file()
    finally:
        scratch.cleanup()

    assert not scratch.root.exists()
    assert not fallback_parent.exists()


def test_cleanup_removes_readonly_external_artifacts(tmp_path: Path) -> None:
    """External tools should not strand scratch files with read-only attributes."""

    scratch = external_scratch.ExternalScratchWorkspace.reserve(tmp_path / "scratch")
    readonly_file = scratch.root / "external-artifact.bin"
    readonly_file.write_bytes(b"artifact")
    readonly_file.chmod(stat.S_IREAD)

    scratch.cleanup()

    assert not scratch.root.exists()


def test_cleanup_refuses_to_remove_an_unowned_directory(tmp_path: Path) -> None:
    """Cleanup should reject an existing directory without its ownership sentinel."""

    unowned_root = tmp_path / "unowned"
    unowned_root.mkdir()
    (unowned_root / "user-file.txt").write_text("preserve", encoding="utf-8")
    scratch = external_scratch.ExternalScratchWorkspace(root=unowned_root)

    with pytest.raises(RuntimeError, match="unowned"):
        scratch.cleanup()

    assert (unowned_root / "user-file.txt").read_text(encoding="utf-8") == "preserve"
