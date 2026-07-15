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

"""Tests for pinned Comfy nodepack source archives."""

from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from substitute.infrastructure.comfy import pinned_nodepack_source
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS


def test_pinned_source_overlay_writes_comfy_registry_tracking_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pinned fallback should preserve Comfy Manager CNR metadata shape."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    source_root = tmp_path / "archive" / "Substitute-BackEnd-1.5.1"
    target_root = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    _write_file(source_root / "__init__.py", "")
    _write_file(source_root / "substitute_backend" / "__init__.py", "")
    _write_file(
        source_root / "pyproject.toml",
        '[project]\nname = "substitute-backend"\nversion = "1.5.1"\n',
    )
    _write_file(source_root / "tests" / "test_ignored.py", "")
    _write_file(source_root / "node_modules" / "package" / "index.js", "")
    _write_file(target_root / "user-extra.txt", "keep")

    def fake_download_file(*, archive_url: str, target_path: Path) -> None:
        """Create a placeholder archive without using the network."""

        _ = archive_url
        target_path.write_text("archive", encoding="utf-8")

    def fake_extract_single_root_zip(*, archive_path: Path, target_path: Path) -> Path:
        """Return the prepared source checkout without extracting an archive."""

        _ = archive_path, target_path
        return source_root

    monkeypatch.setattr(pinned_nodepack_source, "download_file", fake_download_file)
    monkeypatch.setattr(
        pinned_nodepack_source,
        "extract_single_root_zip",
        fake_extract_single_root_zip,
    )

    pinned_nodepack_source.overlay_pinned_source_archive(
        archive_url="https://example.invalid/source.zip",
        target_path=target_root,
        nodepack=nodepack,
        write_registry_tracking=True,
        on_log=None,
    )

    tracked_files = set(
        (target_root / ".tracking").read_text(encoding="utf-8").splitlines()
    )
    assert tracked_files == {
        "__init__.py",
        "pyproject.toml",
        "substitute_backend/__init__.py",
    }
    assert (target_root / "user-extra.txt").read_text(encoding="utf-8") == "keep"
    assert "user-extra.txt" not in tracked_files
    assert not any(path.startswith("tests/") for path in tracked_files)
    assert not any(path.startswith("node_modules/") for path in tracked_files)


def test_pinned_source_overlay_preserves_plain_folder_without_registry_tracking(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Plain fallback folders should not be converted into Registry-managed folders."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    source_root = tmp_path / "archive" / "Substitute-BackEnd-1.5.1"
    target_root = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    _write_file(source_root / "__init__.py", "")
    _write_file(source_root / "substitute_backend" / "__init__.py", "")
    _write_file(
        source_root / "pyproject.toml",
        '[project]\nname = "substitute-backend"\nversion = "1.5.1"\n',
    )

    def fake_download_file(*, archive_url: str, target_path: Path) -> None:
        """Create a placeholder archive without using the network."""

        _ = archive_url
        target_path.write_text("archive", encoding="utf-8")

    def fake_extract_single_root_zip(*, archive_path: Path, target_path: Path) -> Path:
        """Return the prepared source checkout without extracting an archive."""

        _ = archive_path, target_path
        return source_root

    monkeypatch.setattr(pinned_nodepack_source, "download_file", fake_download_file)
    monkeypatch.setattr(
        pinned_nodepack_source,
        "extract_single_root_zip",
        fake_extract_single_root_zip,
    )

    pinned_nodepack_source.overlay_pinned_source_archive(
        archive_url="https://example.invalid/source.zip",
        target_path=target_root,
        nodepack=nodepack,
        write_registry_tracking=False,
        on_log=None,
    )

    assert (target_root / "pyproject.toml").is_file()
    assert not (target_root / ".tracking").exists()


def test_apply_pinned_source_fallback_preserves_registry_tracking_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pinned fallback should overlay Registry-managed folders as Registry-managed."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    target_root = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    _write_file(target_root / "pyproject.toml", "")
    _write_file(target_root / ".tracking", "pyproject.toml")
    overlays: list[tuple[str, Path, bool]] = []

    def fake_overlay_pinned_source_archive(
        *,
        archive_url: str,
        target_path: Path,
        nodepack: object,
        write_registry_tracking: bool,
        on_log: object | None,
        temp_dir: Path | None = None,
    ) -> None:
        """Record pinned overlay requests without touching archives."""

        _ = nodepack, on_log, temp_dir
        overlays.append((archive_url, target_path, write_registry_tracking))

    monkeypatch.setattr(
        pinned_nodepack_source,
        "overlay_pinned_source_archive",
        fake_overlay_pinned_source_archive,
    )

    pinned_nodepack_source.apply_pinned_source_fallback(
        backend_root=target_root,
        archive_url="https://example.invalid/source.zip",
        target_path=target_root,
        nodepack=nodepack,
        on_log=None,
        env=None,
    )

    assert overlays == [("https://example.invalid/source.zip", target_root, True)]


def test_apply_pinned_source_fallback_checks_out_git_tag_without_overlay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pinned fallback should keep git-backed nodepacks git-managed."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    target_root = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    (target_root / ".git").mkdir(parents=True)
    checkouts: list[Path] = []
    overlays: list[str] = []

    def fake_checkout_pinned_git_tag(
        *,
        target_path: Path,
        nodepack: object,
        on_log: object | None,
        env: object | None,
    ) -> None:
        """Record checkout requests without running git."""

        _ = nodepack, on_log, env
        checkouts.append(target_path)

    monkeypatch.setattr(
        pinned_nodepack_source,
        "checkout_pinned_git_tag",
        fake_checkout_pinned_git_tag,
    )
    monkeypatch.setattr(
        pinned_nodepack_source,
        "overlay_pinned_source_archive",
        lambda **kwargs: overlays.append("overlay"),
    )

    pinned_nodepack_source.apply_pinned_source_fallback(
        backend_root=target_root,
        archive_url="https://example.invalid/source.zip",
        target_path=target_root,
        nodepack=nodepack,
        on_log=None,
        env=None,
    )

    assert checkouts == [target_root]
    assert overlays == []


def test_replace_with_pinned_source_archive_replaces_git_checkout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pinned replacement should backup and replace unmergeable git checkouts."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    source_root = tmp_path / "archive" / "Substitute-BackEnd-1.6.2"
    target_root = tmp_path / "custom_nodes" / "Substitute-BackEnd"
    _write_file(source_root / "__init__.py", "new")
    _write_file(source_root / "substitute_backend" / "__init__.py", "new")
    _write_file(source_root / "pyproject.toml", "")
    _write_file(target_root / ".git" / "HEAD", "ref: refs/heads/main\n")
    _write_file(target_root / "old.py", "old")
    backups: list[tuple[Path, str]] = []

    def fake_download_file(*, archive_url: str, target_path: Path) -> None:
        """Create a placeholder archive without using the network."""

        _ = archive_url
        target_path.write_text("archive", encoding="utf-8")

    def fake_extract_single_root_zip(*, archive_path: Path, target_path: Path) -> Path:
        """Return the prepared source checkout without extracting an archive."""

        _ = archive_path, target_path
        return source_root

    def fake_backup_before_replacement(
        *,
        target_path: Path,
        nodepack: object,
        reason: str,
        on_log: object | None,
        env: object | None,
    ) -> None:
        """Record backup requests without invoking git."""

        _ = nodepack, on_log, env
        backups.append((target_path, reason))

    monkeypatch.setattr(pinned_nodepack_source, "download_file", fake_download_file)
    monkeypatch.setattr(
        pinned_nodepack_source,
        "extract_single_root_zip",
        fake_extract_single_root_zip,
    )
    monkeypatch.setattr(
        pinned_nodepack_source,
        "try_backup_git_nodepack_before_replacement",
        fake_backup_before_replacement,
    )

    pinned_nodepack_source.replace_with_pinned_source_archive(
        archive_url="https://example.invalid/source.zip",
        target_path=target_root,
        nodepack=nodepack,
        on_log=None,
        env=None,
    )

    assert backups == [(target_root, "git_fast_forward_failed")]
    assert (target_root / "__init__.py").read_text(encoding="utf-8") == "new"
    assert (target_root / "substitute_backend" / "__init__.py").is_file()
    assert not (target_root / ".git").exists()
    assert not (target_root / "old.py").exists()


def test_extract_single_root_zip_rejects_unsafe_paths(tmp_path: Path) -> None:
    """Pinned archive extraction should fail closed on path traversal entries."""

    archive_path = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("../escape.txt", "unsafe")

    with pytest.raises(RuntimeError, match="unsafe path"):
        pinned_nodepack_source.extract_single_root_zip(
            archive_path=archive_path,
            target_path=tmp_path / "extracted",
        )


def test_extract_single_root_zip_requires_one_root(tmp_path: Path) -> None:
    """Pinned archive extraction should reject archives with multiple roots."""

    archive_path = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("first/file.txt", "first")
        archive.writestr("second/file.txt", "second")

    with pytest.raises(RuntimeError, match="one root folder"):
        pinned_nodepack_source.extract_single_root_zip(
            archive_path=archive_path,
            target_path=tmp_path / "extracted",
        )


def test_extract_single_root_zip_returns_extracted_root(tmp_path: Path) -> None:
    """Pinned archive extraction should return the extracted top-level directory."""

    archive_path = tmp_path / "source.zip"
    target_path = tmp_path / "extracted"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("root/file.txt", "content")
        archive.writestr("root/nested/child.txt", "child")

    source_root = pinned_nodepack_source.extract_single_root_zip(
        archive_path=archive_path,
        target_path=target_path,
    )

    assert source_root == target_path / "root"
    assert (source_root / "file.txt").read_text(encoding="utf-8") == "content"
    assert (source_root / "nested" / "child.txt").read_text(encoding="utf-8") == (
        "child"
    )


def test_write_registry_tracking_file_uses_registry_path_format(tmp_path: Path) -> None:
    """Registry tracking metadata should use forward-slash relative paths."""

    target_path = tmp_path / "nodepack"
    target_path.mkdir()

    pinned_nodepack_source.write_registry_tracking_file(
        target_path=target_path,
        tracked_files=(Path("pkg") / "module.py", Path("pyproject.toml")),
    )

    assert (target_path / ".tracking").read_text(encoding="utf-8") == (
        "pkg/module.py\npyproject.toml"
    )


def test_temp_dir_from_env_creates_managed_temp_override(tmp_path: Path) -> None:
    """Pinned source temp folders should honor managed subprocess temp env values."""

    temp_path = tmp_path / "temp"

    assert (
        pinned_nodepack_source.temp_dir_from_env({"TEMP": str(temp_path)}) == temp_path
    )
    assert temp_path.is_dir()
    assert pinned_nodepack_source.temp_dir_from_env({}) is None
    assert pinned_nodepack_source.temp_dir_from_env(None) is None


def _write_file(path: Path, content: str) -> None:
    """Write a test fixture file, creating parents first."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
