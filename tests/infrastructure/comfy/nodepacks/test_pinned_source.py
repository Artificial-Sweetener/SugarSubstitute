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

"""Tests for CNR-compatible pinned nodepack fallback and migration."""

from __future__ import annotations

import io
from pathlib import Path
import shutil
import ssl
from urllib.error import URLError
import zipfile

import pytest

from substitute.infrastructure.comfy import pinned_nodepack_source
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from substitute.infrastructure.comfy.pinned_nodepack_source import (
    PinnedNodepackSourceInstaller,
)
from sugarsubstitute_shared.tls import SystemTrustTlsContext


def test_pinned_archive_download_uses_system_trust_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Honor native certificate administration for trusted fallback downloads."""

    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    observed: list[ssl.SSLContext] = []

    def fake_urlopen(
        _request: object,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> io.BytesIO:
        """Return deterministic content while recording transport policy."""

        assert timeout > 0
        observed.append(context)
        return io.BytesIO(b"archive")

    monkeypatch.setattr(SystemTrustTlsContext, "create", lambda: tls_context)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    pinned_nodepack_source.download_file(
        archive_url="https://github.example/source.zip",
        target_path=tmp_path / "source.zip",
    )

    assert (tmp_path / "source.zip").read_bytes() == b"archive"
    assert observed == [tls_context]


def test_pinned_archive_download_recovers_from_transient_transport_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Retry a bounded transport interruption and expose each retry to setup UI."""

    attempts = 0
    messages: list[str] = []
    delays: list[float] = []

    def flaky_urlopen(
        _request: object,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> io.BytesIO:
        """Fail twice like the release runner before returning the archive."""

        del timeout, context
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise URLError(ConnectionResetError("simulated transport interruption"))
        return io.BytesIO(b"archive")

    monkeypatch.setattr("urllib.request.urlopen", flaky_urlopen)
    monkeypatch.setattr(
        pinned_nodepack_source,
        "_DOWNLOAD_RETRY_DELAYS_SECONDS",
        (0.25, 0.75),
        raising=False,
    )
    monkeypatch.setattr(
        pinned_nodepack_source,
        "_sleep",
        delays.append,
        raising=False,
    )

    pinned_nodepack_source.download_file(
        archive_url="https://github.example/source.zip",
        target_path=tmp_path / "source.zip",
        on_log=messages.append,
    )

    assert attempts == 3
    assert delays == [0.25, 0.75]
    assert (tmp_path / "source.zip").read_bytes() == b"archive"
    assert len(messages) == 2
    assert all("retrying" in message.casefold() for message in messages)
    assert "2 of 3" in messages[0]
    assert "3 of 3" in messages[1]


def test_pinned_archive_download_exhausts_a_bounded_retry_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Stop after the declared attempts and leave no partial archive behind."""

    attempts = 0
    messages: list[str] = []
    delays: list[float] = []

    def unavailable_urlopen(
        _request: object,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> io.BytesIO:
        """Represent a transport that remains unavailable for every attempt."""

        del timeout, context
        nonlocal attempts
        attempts += 1
        raise URLError(TimeoutError("simulated timeout"))

    monkeypatch.setattr("urllib.request.urlopen", unavailable_urlopen)
    monkeypatch.setattr(
        pinned_nodepack_source,
        "_DOWNLOAD_RETRY_DELAYS_SECONDS",
        (0.25, 0.75),
    )
    monkeypatch.setattr(pinned_nodepack_source, "_sleep", delays.append)
    target = tmp_path / "source.zip"

    with pytest.raises(URLError):
        pinned_nodepack_source.download_file(
            archive_url="https://github.example/source.zip",
            target_path=target,
            on_log=messages.append,
        )

    assert attempts == 3
    assert delays == [0.25, 0.75]
    assert len(messages) == 2
    assert not target.exists()


def test_pinned_archive_download_does_not_retry_non_transport_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Propagate a local programming or filesystem failure without disguising it."""

    attempts = 0
    messages: list[str] = []
    delays: list[float] = []

    def invalid_urlopen(
        _request: object,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> io.BytesIO:
        """Raise a non-transport failure on the first request."""

        del timeout, context
        nonlocal attempts
        attempts += 1
        raise ValueError("simulated local failure")

    monkeypatch.setattr("urllib.request.urlopen", invalid_urlopen)
    monkeypatch.setattr(pinned_nodepack_source, "_sleep", delays.append)

    with pytest.raises(ValueError, match="simulated local failure"):
        pinned_nodepack_source.download_file(
            archive_url="https://github.example/source.zip",
            target_path=tmp_path / "source.zip",
            on_log=messages.append,
        )

    assert attempts == 1
    assert delays == []
    assert messages == []


def test_fallback_install_is_registry_owned_and_preserves_mutable_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Overlay only source-owned files and retain user/runtime nodepack state."""

    nodepack = CORE_COMFY_NODEPACKS[1]
    source = tmp_path / "release"
    target = tmp_path / nodepack.expected_folder
    _materialize_release(source, nodepack_index=1, marker="new")
    _write(target / "obsolete.py", "old")
    _write(target / ".tracking", "obsolete.py")
    _write(target / ".sugarcubes" / "Base-Cubes" / "local.cube", "user")
    _write(target / ".generated" / "catalog.json", "runtime")
    _write(source / "tests" / "test_ignored.py", "ignored")
    _patch_archive_source(monkeypatch, source)

    PinnedNodepackSourceInstaller().install_fallback(
        target_path=target,
        nodepack=nodepack,
        on_log=None,
        env=None,
    )

    tracked = set((target / ".tracking").read_text(encoding="utf-8").splitlines())
    assert "obsolete.py" not in tracked
    assert not (target / "obsolete.py").exists()
    assert (target / "__init__.py").read_text(encoding="utf-8") == "new"
    assert (target / ".sugarcubes" / "Base-Cubes" / "local.cube").read_text(
        encoding="utf-8"
    ) == "user"
    assert (target / ".generated" / "catalog.json").read_text(
        encoding="utf-8"
    ) == "runtime"
    assert not (target / "tests").exists()
    assert not any(path.startswith(".sugarcubes/") for path in tracked)


def test_fallback_transaction_restores_previous_owned_source_on_copy_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Restore both source and ownership metadata after a partial overlay failure."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    source = tmp_path / "release"
    target = tmp_path / nodepack.expected_folder
    _materialize_release(source, nodepack_index=0, marker="new")
    _write(target / "old.py", "old")
    _write(target / ".tracking", "old.py")
    _write(target / "cache" / "preserved.json", "cache")
    _patch_archive_source(monkeypatch, source)
    real_copy = shutil.copy2

    def failing_copy(source_path: Path, destination: Path) -> str:
        """Fail only while copying one new release file into the target."""

        if Path(source_path) == source / "substitute_backend" / "__init__.py":
            raise OSError("forced copy failure")
        return str(real_copy(source_path, destination))

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.pinned_nodepack_source.shutil.copy2",
        failing_copy,
    )

    with pytest.raises(OSError, match="forced copy failure"):
        PinnedNodepackSourceInstaller().install_fallback(
            target_path=target,
            nodepack=nodepack,
            on_log=None,
            env=None,
        )

    assert (target / "old.py").read_text(encoding="utf-8") == "old"
    assert (target / ".tracking").read_text(encoding="utf-8") == "old.py"
    assert (target / "cache" / "preserved.json").read_text(encoding="utf-8") == (
        "cache"
    )
    assert not (target / "substitute_backend" / "__init__.py").exists()


def test_extract_single_root_zip_rejects_unsafe_paths(tmp_path: Path) -> None:
    """Fail closed on an archive path traversal entry."""

    archive_path = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("../escape.txt", "unsafe")

    with pytest.raises(RuntimeError, match="unsafe path"):
        pinned_nodepack_source.extract_single_root_zip(
            archive_path=archive_path,
            target_path=tmp_path / "extracted",
        )


def _patch_archive_source(
    monkeypatch: pytest.MonkeyPatch,
    source: Path,
) -> None:
    """Route one fallback operation to a prepared release fixture."""

    monkeypatch.setattr(
        pinned_nodepack_source,
        "download_file",
        lambda **kwargs: Path(kwargs["target_path"]).write_bytes(b"archive"),
    )
    monkeypatch.setattr(
        pinned_nodepack_source,
        "extract_single_root_zip",
        lambda **kwargs: source,
    )


def _materialize_release(root: Path, *, nodepack_index: int, marker: str) -> None:
    """Create one exact trusted release source tree."""

    nodepack = CORE_COMFY_NODEPACKS[nodepack_index]
    for sentinel in nodepack.sentinel_files:
        _write(root / sentinel, marker)
    package = "substitute_backend" if nodepack_index == 0 else "sugarcubes"
    _write(root / package / "__init__.py", marker)
    _write(
        root / "pyproject.toml",
        (
            "[project]\n"
            f'name = "{nodepack.registry_id}"\n'
            f'version = "{nodepack.required_version}"\n'
            "dependencies = []\n"
            "[project.urls]\n"
            f'Repository = "{nodepack.fallback_repository_url.removesuffix(".git")}"\n'
        ),
    )


def _write(path: Path, content: str) -> None:
    """Write a fixture file with its parents."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
