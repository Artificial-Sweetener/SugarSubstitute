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

"""Verify complete staged-tree identity and tamper detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.repair import (
    RepairArtifactIntegrityError,
    directory_tree_sha256,
    verify_directory_tree_sha256,
)


def test_tree_digest_detects_content_and_path_tampering(tmp_path: Path) -> None:
    """Any staged file mutation should invalidate its preparation receipt."""

    staged = tmp_path / "staged"
    staged.mkdir()
    artifact = staged / "launcher.exe"
    artifact.write_bytes(b"verified")
    digest = directory_tree_sha256(staged)

    verify_directory_tree_sha256(staged, expected=digest)
    artifact.write_bytes(b"tampered")

    with pytest.raises(RepairArtifactIntegrityError, match="integrity mismatch"):
        verify_directory_tree_sha256(staged, expected=digest)


def test_tree_digest_accepts_and_hashes_internal_symbolic_links(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A portable internal link should be represented without being traversed."""

    staged = tmp_path / "staged"
    staged.mkdir()
    target = staged / "python3"
    target.write_bytes(b"runtime")
    link = staged / "python"
    link.write_bytes(b"representative-link-entry")
    _represent_link(monkeypatch, link=link, target=Path("python3"))
    digest = directory_tree_sha256(staged)

    assert directory_tree_sha256(staged) == digest
    target.write_bytes(b"changed")
    assert directory_tree_sha256(staged) != digest


def test_tree_digest_rejects_symbolic_link_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A link must never redirect detached validation outside staging."""

    staged = tmp_path / "staged"
    staged.mkdir()
    external = tmp_path / "external.txt"
    external.write_bytes(b"external")
    link = staged / "link.txt"
    link.write_bytes(b"representative-link-entry")
    _represent_link(
        monkeypatch,
        link=link,
        target=Path("..") / external.name,
    )

    with pytest.raises(RepairArtifactIntegrityError, match="escapes staging"):
        directory_tree_sha256(staged)


def _represent_link(
    monkeypatch: pytest.MonkeyPatch,
    *,
    link: Path,
    target: Path,
) -> None:
    """Represent a symlink portably when Windows developer mode is unavailable."""

    original_is_symlink = Path.is_symlink
    original_readlink = Path.readlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == link or original_is_symlink(path),
    )
    monkeypatch.setattr(
        Path,
        "readlink",
        lambda path: target if path == link else original_readlink(path),
    )
