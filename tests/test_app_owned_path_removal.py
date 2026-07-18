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

"""Verify cross-platform removal of application-owned filesystem paths."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import stat

import pytest

from substitute.infrastructure.filesystem.path_removal import remove_app_owned_path

RemovalOperation = Callable[[str], object]
RemovalErrorHandler = Callable[[RemovalOperation, str, BaseException], None]


def test_remove_app_owned_path_ignores_a_missing_path(tmp_path: Path) -> None:
    """Cleanup should be idempotent when its owned target is absent."""

    remove_app_owned_path(tmp_path / "missing")


def test_remove_app_owned_path_unlinks_a_file(tmp_path: Path) -> None:
    """A non-directory owned path should be unlinked directly."""

    owned_file = tmp_path / "owned.txt"
    owned_file.write_text("owned", encoding="utf-8")

    remove_app_owned_path(owned_file)

    assert not owned_file.exists()


def test_remove_app_owned_path_removes_a_directory_tree(tmp_path: Path) -> None:
    """A normal directory tree should be removed recursively."""

    owned_root = tmp_path / "owned"
    nested_file = owned_root / "nested" / "data.txt"
    nested_file.parent.mkdir(parents=True)
    nested_file.write_text("owned", encoding="utf-8")

    remove_app_owned_path(owned_root)

    assert not owned_root.exists()


def test_permission_retry_preserves_existing_mode_bits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Permission repair should add owner access without replacing other bits."""

    owned_root = tmp_path / "owned"
    owned_root.mkdir()
    locked_file = owned_root / "locked.pack"
    locked_file.write_text("pack", encoding="utf-8")
    locked_file.chmod(stat.S_IRUSR | stat.S_IRGRP)
    original_mode = locked_file.stat().st_mode
    chmod_calls: list[tuple[Path, int]] = []
    retried_paths: list[Path] = []

    def record_retry(failed_path: str) -> None:
        """Record the path received by the retried operation."""

        retried_paths.append(Path(failed_path))

    def simulate_permission_failure(
        _path: Path,
        *,
        onexc: RemovalErrorHandler,
    ) -> None:
        """Exercise the real permission callback without deleting the fixture."""

        onexc(record_retry, str(locked_file), PermissionError("read only"))

    monkeypatch.setattr(
        "substitute.infrastructure.filesystem.path_removal.shutil.rmtree",
        simulate_permission_failure,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.filesystem.path_removal.os.chmod",
        lambda path, mode: chmod_calls.append((Path(path), mode)),
    )

    remove_app_owned_path(owned_root)

    assert chmod_calls[0] == (locked_file, original_mode | stat.S_IWUSR)
    assert retried_paths == [locked_file]


def test_remove_app_owned_path_reraises_unrelated_rmtree_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cleanup should not reinterpret non-permission filesystem failures."""

    owned_root = tmp_path / "owned"
    owned_root.mkdir()
    expected_error = OSError("storage failure")

    def simulate_unrelated_failure(
        _path: Path,
        *,
        onexc: RemovalErrorHandler,
    ) -> None:
        """Pass an unrelated failure through the configured callback."""

        onexc(lambda _failed_path: None, str(owned_root), expected_error)

    monkeypatch.setattr(
        "substitute.infrastructure.filesystem.path_removal.shutil.rmtree",
        simulate_unrelated_failure,
    )

    with pytest.raises(OSError) as raised:
        remove_app_owned_path(owned_root)

    assert raised.value is expected_error


def test_remove_app_owned_path_reraises_a_failed_permission_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cleanup should retry permission failures once and expose repeat failure."""

    owned_root = tmp_path / "owned"
    owned_root.mkdir()
    locked_file = owned_root / "locked.pack"
    locked_file.write_text("pack", encoding="utf-8")
    expected_error = PermissionError("still locked")

    def fail_retry(_failed_path: str) -> None:
        """Represent an operation that remains blocked after mode repair."""

        raise expected_error

    def simulate_permission_failure(
        _path: Path,
        *,
        onexc: RemovalErrorHandler,
    ) -> None:
        """Pass a permission failure through the configured callback."""

        onexc(fail_retry, str(locked_file), PermissionError("read only"))

    monkeypatch.setattr(
        "substitute.infrastructure.filesystem.path_removal.shutil.rmtree",
        simulate_permission_failure,
    )

    with pytest.raises(PermissionError) as raised:
        remove_app_owned_path(owned_root)

    assert raised.value is expected_error


@pytest.mark.platforms("windows")
def test_windows_removes_readonly_git_pack_files(tmp_path: Path) -> None:
    """Windows cleanup should clear Git pack read-only attributes and remove them."""

    owned_root = tmp_path / "ComfyUI-Manager"
    pack_root = owned_root / ".git" / "objects" / "pack"
    pack_root.mkdir(parents=True)
    for extension in ("idx", "pack", "rev"):
        pack_file = pack_root / f"pack-fixture.{extension}"
        pack_file.write_bytes(b"pack fixture")
        pack_file.chmod(stat.S_IREAD)
        assert pack_file.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY

    remove_app_owned_path(owned_root)

    assert not owned_root.exists()


@pytest.mark.platforms("linux", "macos")
def test_posix_repairs_unwritable_owned_directories(tmp_path: Path) -> None:
    """POSIX cleanup should restore owner traversal and deletion permissions."""

    owned_root = tmp_path / "owned"
    locked_directory = owned_root / "locked"
    locked_directory.mkdir(parents=True)
    (locked_directory / "data.txt").write_text("owned", encoding="utf-8")
    locked_directory.chmod(stat.S_IRUSR | stat.S_IXUSR)

    try:
        remove_app_owned_path(owned_root)
    finally:
        if locked_directory.exists():
            locked_directory.chmod(stat.S_IRWXU)

    assert not owned_root.exists()


@pytest.mark.platforms("linux", "macos")
def test_posix_unlinks_directory_symlink_without_traversing_target(
    tmp_path: Path,
) -> None:
    """Root symlink cleanup should retain the directory it references."""

    target = tmp_path / "user-owned-target"
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    owned_link = tmp_path / "app-owned-link"
    owned_link.symlink_to(target, target_is_directory=True)

    remove_app_owned_path(owned_link)

    assert not owned_link.exists()
    assert sentinel.read_text(encoding="utf-8") == "keep"
