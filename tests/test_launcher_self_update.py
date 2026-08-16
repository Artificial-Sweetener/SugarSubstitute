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

"""Regression tests for staged, transactional launcher self-updates."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import ssl
import stat
import subprocess
import sys
import time
from typing import cast
import zipfile

import pytest

from substitute.infrastructure.launcher_update.legacy_bridge import (
    LegacyLauncherUpdateBridge,
)
from sugarsubstitute_shared.launcher_update.archive import SecureArchiveError
from sugarsubstitute_shared.launcher_update.downloader import LauncherBundleDownloader
from sugarsubstitute_shared.launcher_update.models import (
    LauncherBundleAsset,
    LauncherInstallationRecord,
    LauncherUpdateRequest,
)
from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager
from sugarsubstitute_shared.launcher_update.targets import (
    LINUX_X64_BUNDLE,
    MACOS_ARM64_BUNDLE,
    WINDOWS_X64_BUNDLE,
)
from sugarsubstitute_shared.launcher_update.transaction import (
    LauncherUpdateTransaction,
    LauncherUpdateTransactionError,
)
import sugarsubstitute_shared.launcher_update.transaction as transaction_module
import sugarsubstitute_shared.launcher_update.process as update_process_module


def test_launcher_bundle_download_uses_explicit_system_trust_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Launcher replacement downloads must share the verified TLS policy."""

    content = b"launcher bundle"
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    observed: list[tuple[float, ssl.SSLContext]] = []

    def fake_urlopen(
        _request: object,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> io.BytesIO:
        """Record the HTTPS context and return one in-memory bundle."""

        observed.append((timeout, context))
        return io.BytesIO(content)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    destination = tmp_path / "launcher.zip"

    result = LauncherBundleDownloader(
        timeout_seconds=15.0,
        tls_context=tls_context,
    ).download(
        asset=LauncherBundleAsset(
            filename="launcher.zip",
            url="https://github.example/launcher.zip",
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        ),
        destination=destination,
    )

    assert result == destination
    assert destination.read_bytes() == content
    assert observed == [(15.0, tls_context)]


def test_launcher_update_helper_does_not_inherit_frozen_parent_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The runtime-Python updater helper must not inherit PyInstaller libraries."""

    meipass = tmp_path / "_MEI-update"
    bundled_library = meipass / "libpython.dylib"
    system_library = tmp_path / "system-library"
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(
        "sugarsubstitute_shared.subprocess_environment.os.environ",
        {
            "PATH": f"{meipass}{os.pathsep}{tmp_path}",
            "DYLD_LIBRARY_PATH": str(bundled_library),
            "DYLD_LIBRARY_PATH_ORIG": str(system_library),
            "_PYI_APPLICATION_HOME_DIR": str(meipass),
            "QUALIFICATION_TOKEN": "preserved",
        },
    )
    observed_environment: dict[str, str] = {}

    class _Process:
        """Represent the scheduled updater helper."""

        pid = 42

    def fake_popen(*_args: object, **kwargs: object) -> _Process:
        """Capture the environment passed across the helper boundary."""

        observed_environment.update(cast(dict[str, str], kwargs["env"]))
        return _Process()

    monkeypatch.setattr(
        "sugarsubstitute_shared.launcher_update.process.subprocess.Popen",
        fake_popen,
    )
    request_path, runtime_python, app_dir = _write_scheduled_update_request(tmp_path)

    update_process_module.schedule_launcher_update(
        request_path=request_path,
        runtime_python=runtime_python,
        app_dir=app_dir,
        relaunch=True,
        wait_pid=123,
    )

    assert str(meipass) not in observed_environment["PATH"].split(os.pathsep)
    assert observed_environment["DYLD_LIBRARY_PATH"] == str(system_library)
    assert "DYLD_LIBRARY_PATH_ORIG" not in observed_environment
    assert "_PYI_APPLICATION_HOME_DIR" not in observed_environment
    assert observed_environment["QUALIFICATION_TOKEN"] == "preserved"


def test_stager_verifies_and_persists_complete_bundle(tmp_path: Path) -> None:
    """A checksum-pinned target bundle should become one pending request."""

    install_root = tmp_path / "SugarSubstitute"
    archive = _write_bundle(tmp_path / "launcher.zip", marker="new")

    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version="0.11.0",
        target=WINDOWS_X64_BUNDLE,
        asset=_asset(archive),
    )

    request = LauncherUpdateRequest.load(request_path)
    assert request.install_root == install_root.resolve()
    assert request.version == "0.11.0"
    assert (request.staged_bundle_dir / "SugarSubstitute.exe").read_text() == "new"
    assert (request.staged_bundle_dir / "launcher-bin" / "runtime.txt").is_file()


def test_stager_rejects_archive_path_traversal(tmp_path: Path) -> None:
    """A launcher archive must never write outside its staging directory."""

    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escaped.txt", "bad")

    with pytest.raises(SecureArchiveError):
        LauncherBundleStager().stage(
            install_root=tmp_path / "SugarSubstitute",
            version="0.11.0",
            target=WINDOWS_X64_BUNDLE,
            asset=_asset(archive),
        )

    assert not (tmp_path / "escaped.txt").exists()


def test_stager_rejects_symlink_target_that_escapes_bundle(tmp_path: Path) -> None:
    """A launcher symlink may never resolve outside its staged bundle."""

    archive = tmp_path / "unsafe-link.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        link = zipfile.ZipInfo("SugarSubstitute.app/Contents/Frameworks/Python")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr(link, "../../../../outside")

    with pytest.raises(SecureArchiveError, match="target escapes"):
        LauncherBundleStager().stage(
            install_root=tmp_path / "SugarSubstitute",
            version="0.11.0",
            target=MACOS_ARM64_BUNDLE,
            asset=_asset(archive),
        )

    assert not (tmp_path / "outside").exists()


@pytest.mark.platforms("linux", "macos")
def test_stager_restores_safe_relative_macos_symlinks(tmp_path: Path) -> None:
    """Staging should reconstruct a PyInstaller-style macOS framework link."""

    archive = tmp_path / "macos-launcher.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(
            "SugarSubstitute.app/Contents/MacOS/SugarSubstitute",
            "launcher",
        )
        bundle.writestr(
            "SugarSubstitute.app/Contents/Frameworks/"
            "Python.framework/Versions/3.13/Python",
            "runtime",
        )
        link = zipfile.ZipInfo(
            "SugarSubstitute.app/Contents/Frameworks/Python.framework/Versions/Current"
        )
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr(link, "3.13")

    request_path = LauncherBundleStager().stage(
        install_root=tmp_path / "SugarSubstitute",
        version="0.11.0",
        target=MACOS_ARM64_BUNDLE,
        asset=_asset(archive),
    )
    request = LauncherUpdateRequest.load(request_path)
    restored_link = (
        request.staged_bundle_dir
        / "SugarSubstitute.app"
        / "Contents"
        / "Frameworks"
        / "Python.framework"
        / "Versions"
        / "Current"
    )

    assert restored_link.is_symlink()
    assert restored_link.readlink() == Path("3.13")


@pytest.mark.platforms("linux", "macos")
def test_transaction_preserves_macos_symlinks_during_promotion(tmp_path: Path) -> None:
    """Promotion must retain the staged PyInstaller bundle topology."""

    install_root = tmp_path / "SugarSubstitute"
    old_app = install_root / "SugarSubstitute.app" / "Contents"
    (old_app / "MacOS").mkdir(parents=True)
    (old_app / "MacOS" / "SugarSubstitute").write_text(
        "old launcher",
        encoding="utf-8",
    )
    (old_app / "Frameworks").mkdir()
    archive = tmp_path / "macos-launcher.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(
            "SugarSubstitute.app/Contents/MacOS/SugarSubstitute",
            "new launcher",
        )
        bundle.writestr(
            "SugarSubstitute.app/Contents/Frameworks/"
            "Python.framework/Versions/3.13/Python",
            "runtime",
        )
        link = zipfile.ZipInfo(
            "SugarSubstitute.app/Contents/Frameworks/Python.framework/Versions/Current"
        )
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr(link, "3.13")

    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version="0.11.0",
        target=MACOS_ARM64_BUNDLE,
        asset=_asset(archive),
    )
    LauncherUpdateTransaction(wait_timeout_seconds=0).apply(request_path=request_path)
    promoted_link = (
        install_root
        / "SugarSubstitute.app"
        / "Contents"
        / "Frameworks"
        / "Python.framework"
        / "Versions"
        / "Current"
    )

    assert promoted_link.is_symlink()
    assert promoted_link.readlink() == Path("3.13")


@pytest.mark.platforms("linux", "macos")
def test_stager_restores_linux_launcher_executable_mode(tmp_path: Path) -> None:
    """Portable extraction must leave the installed Linux launcher runnable."""

    archive = tmp_path / "linux-launcher.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        executable = zipfile.ZipInfo("SugarSubstitute")
        executable.external_attr = 0o100644 << 16
        bundle.writestr(executable, b"launcher")
        bundle.writestr("launcher-bin/runtime.txt", b"support")

    request_path = LauncherBundleStager().stage(
        install_root=tmp_path / "SugarSubstitute",
        version="0.11.0",
        target=LINUX_X64_BUNDLE,
        asset=_asset(archive),
    )
    request = LauncherUpdateRequest.load(request_path)
    installed_mode = (
        request.staged_bundle_dir / "SugarSubstitute"
    ).stat().st_mode & 0o777

    assert installed_mode == 0o755


def test_transaction_replaces_only_launcher_and_preserves_install_data(
    tmp_path: Path,
) -> None:
    """Launcher promotion must preserve app, runtime, Comfy, and user content."""

    install_root = _write_installed_layout(tmp_path / "SugarSubstitute")
    archive = _write_bundle(tmp_path / "launcher.zip", marker="new launcher")
    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version="0.11.0",
        target=WINDOWS_X64_BUNDLE,
        asset=_asset(archive),
    )

    LauncherUpdateTransaction(wait_timeout_seconds=0).apply(request_path=request_path)

    assert (install_root / "SugarSubstitute.exe").read_text() == "new launcher"
    assert (install_root / "launcher-bin" / "runtime.txt").read_text() == "new"
    for relative_path in (
        "app/preserve.txt",
        "runtime/preserve.txt",
        "comfyui/preserve.txt",
        "user/preserve.txt",
        "appdata/preserve.txt",
    ):
        assert (install_root / relative_path).read_text() == "preserved"
    assert LauncherInstallationRecord.load(
        install_root / "launcher" / "installation.json"
    ) == LauncherInstallationRecord(version="0.11.0", target_key="windows_x64")
    assert not request_path.exists()


def test_transaction_rolls_back_both_bundle_roots_on_copy_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A partial two-root Windows promotion must restore the old bundle."""

    install_root = _write_installed_layout(tmp_path / "SugarSubstitute")
    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version="0.11.0",
        target=WINDOWS_X64_BUNDLE,
        asset=_asset(_write_bundle(tmp_path / "launcher.zip", marker="new")),
    )
    original_copy = transaction_module._copy_path
    calls = 0

    def fail_second_copy(*, source: Path, destination: Path) -> None:
        """Fail after the executable has already been promoted."""

        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated lock")
        original_copy(source=source, destination=destination)

    monkeypatch.setattr(transaction_module, "_copy_path", fail_second_copy)

    with pytest.raises(LauncherUpdateTransactionError):
        LauncherUpdateTransaction(wait_timeout_seconds=0).apply(
            request_path=request_path
        )

    assert (install_root / "SugarSubstitute.exe").read_text() == "old launcher"
    assert (install_root / "launcher-bin" / "runtime.txt").read_text() == "old"


def test_transaction_recovers_interrupted_backup_before_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A later helper should recover the original bundle before another attempt."""

    install_root = _write_installed_layout(tmp_path / "SugarSubstitute")
    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version="0.11.0",
        target=WINDOWS_X64_BUNDLE,
        asset=_asset(_write_bundle(tmp_path / "launcher.zip", marker="new")),
    )
    update_root = install_root / "launcher" / "updates"
    backup_root = update_root / "backup"
    backup_root.mkdir(parents=True)
    (install_root / "SugarSubstitute.exe").replace(backup_root / "SugarSubstitute.exe")
    (install_root / "launcher-bin").replace(backup_root / "launcher-bin")
    (install_root / "SugarSubstitute.exe").write_text(
        "interrupted partial", encoding="utf-8"
    )
    (install_root / "launcher-bin").mkdir()
    (install_root / "launcher-bin" / "runtime.txt").write_text(
        "interrupted partial", encoding="utf-8"
    )
    (update_root / "transaction.json").write_text(
        '{"phase":"promoting","target_key":"windows_x64"}\n',
        encoding="utf-8",
    )

    def fail_copy(*, source: Path, destination: Path) -> None:
        """Fail the retry so assertions expose the recovered rollback source."""

        _ = source
        _ = destination
        raise OSError("simulated retry failure")

    monkeypatch.setattr(transaction_module, "_copy_path", fail_copy)

    with pytest.raises(LauncherUpdateTransactionError):
        LauncherUpdateTransaction(wait_timeout_seconds=0).apply(
            request_path=request_path
        )

    assert (install_root / "SugarSubstitute.exe").read_text() == "old launcher"
    assert (install_root / "launcher-bin" / "runtime.txt").read_text() == "old"


def test_first_install_rollback_removes_targets_that_were_initially_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed first install must not leave half of a launcher bundle behind."""

    install_root = (tmp_path / "SugarSubstitute").resolve()
    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version="0.11.0",
        target=WINDOWS_X64_BUNDLE,
        asset=_asset(_write_bundle(tmp_path / "launcher.zip", marker="new")),
    )
    original_copy = transaction_module._copy_path
    calls = 0

    def fail_second_copy(*, source: Path, destination: Path) -> None:
        """Fail after placing the initially absent executable."""

        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated first-install failure")
        original_copy(source=source, destination=destination)

    monkeypatch.setattr(transaction_module, "_copy_path", fail_second_copy)

    with pytest.raises(LauncherUpdateTransactionError):
        LauncherUpdateTransaction(wait_timeout_seconds=0).apply(
            request_path=request_path
        )

    assert not (install_root / "SugarSubstitute.exe").exists()
    assert not (install_root / "launcher-bin").exists()


def test_transaction_rejects_staging_outside_install_root(tmp_path: Path) -> None:
    """A forged request cannot promote arbitrary filesystem content."""

    install_root = _write_installed_layout(tmp_path / "SugarSubstitute")
    staged = tmp_path / "outside"
    _write_bundle_tree(staged, marker="malicious")
    request_path = install_root / "launcher" / "updates" / "pending.json"
    LauncherUpdateRequest(
        install_root=install_root,
        version="0.11.0",
        target_key="windows_x64",
        staged_bundle_dir=staged,
        relaunch=False,
    ).save(request_path)

    with pytest.raises(LauncherUpdateTransactionError):
        LauncherUpdateTransaction(wait_timeout_seconds=0).apply(
            request_path=request_path
        )


@pytest.mark.platforms("windows")
def test_windows_process_probe_does_not_terminate_waited_process() -> None:
    """Checking a launcher PID on Windows must never signal or terminate it."""

    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", "import time; time.sleep(30)"],
    )
    try:
        assert transaction_module._process_exists(process.pid) is True
        time.sleep(0.1)
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=10.0)


def test_legacy_bridge_schedules_missing_installation_record(tmp_path: Path) -> None:
    """An updated app should automatically migrate an old installed launcher."""

    install_root = _write_installed_layout(tmp_path / "SugarSubstitute")
    runtime_python = install_root / "runtime" / ".venv" / "Scripts" / "python.exe"
    runtime_python.parent.mkdir(parents=True, exist_ok=True)
    runtime_python.write_text("python", encoding="utf-8")
    (install_root / "app" / "main.py").write_text("", encoding="utf-8")
    _write_launcher_config(install_root, runtime_python=runtime_python)
    archive = _write_bundle(tmp_path / "launcher.zip", marker="new")
    scheduled: list[dict[str, object]] = []

    def schedule(**kwargs: object) -> int:
        """Record one helper scheduling request."""

        scheduled.append(kwargs)
        return 1234

    bridge = LegacyLauncherUpdateBridge(
        target_detector=lambda: WINDOWS_X64_BUNDLE,
        manifest_loader=lambda _url: _manifest_payload(archive),
        scheduler=schedule,
    )

    assert bridge.run(install_root=install_root) is True

    assert len(scheduled) == 1
    assert scheduled[0]["runtime_python"] == runtime_python.resolve()
    assert scheduled[0]["relaunch"] is False
    assert scheduled[0]["wait_pid"] is None


def test_legacy_bridge_does_not_reschedule_current_launcher(tmp_path: Path) -> None:
    """A current installation record should end legacy bridge ownership."""

    install_root = _write_installed_layout(tmp_path / "SugarSubstitute")
    runtime_python = install_root / "runtime" / ".venv" / "Scripts" / "python.exe"
    runtime_python.parent.mkdir(parents=True, exist_ok=True)
    runtime_python.write_text("python", encoding="utf-8")
    (install_root / "app" / "main.py").write_text("", encoding="utf-8")
    _write_launcher_config(install_root, runtime_python=runtime_python)
    LauncherInstallationRecord(
        version="0.11.0",
        target_key="windows_x64",
    ).save(install_root / "launcher" / "installation.json")
    archive = _write_bundle(tmp_path / "launcher.zip", marker="new")
    scheduled: list[object] = []

    def schedule(**kwargs: object) -> int:
        """Record any unexpected helper scheduling request."""

        scheduled.append(kwargs)
        return 1234

    bridge = LegacyLauncherUpdateBridge(
        target_detector=lambda: WINDOWS_X64_BUNDLE,
        manifest_loader=lambda _url: _manifest_payload(archive),
        scheduler=schedule,
    )

    assert bridge.run(install_root=install_root) is False
    assert scheduled == []


def _write_installed_layout(root: Path) -> Path:
    """Create an old Windows launcher plus unrelated preserved install content."""

    root.mkdir(parents=True)
    (root / "SugarSubstitute.exe").write_text("old launcher", encoding="utf-8")
    (root / "launcher-bin").mkdir()
    (root / "launcher-bin" / "runtime.txt").write_text("old", encoding="utf-8")
    for relative_path in (
        "app/preserve.txt",
        "runtime/preserve.txt",
        "comfyui/preserve.txt",
        "user/preserve.txt",
        "appdata/preserve.txt",
    ):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("preserved", encoding="utf-8")
    return root.resolve()


def _write_scheduled_update_request(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Write the minimum valid request needed to schedule an updater helper."""

    install_root = tmp_path / "SugarSubstitute"
    app_dir = install_root / "app"
    runtime_python = install_root / "runtime" / ".venv" / "bin" / "python"
    request_path = install_root / "launcher" / "updates" / "pending.json"
    staged_bundle = install_root / "launcher" / "updates" / "staged"
    app_dir.mkdir(parents=True)
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("python", encoding="utf-8")
    staged_bundle.mkdir(parents=True)
    LauncherUpdateRequest(
        install_root=install_root,
        version="9999.0.1",
        target_key="linux_x64",
        staged_bundle_dir=staged_bundle,
        relaunch=False,
    ).save(request_path)
    return request_path, runtime_python, app_dir


def _write_bundle(path: Path, *, marker: str) -> Path:
    """Write one valid Windows launcher bundle ZIP."""

    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("SugarSubstitute.exe", marker)
        bundle.writestr("launcher-bin/runtime.txt", "new")
    return path


def _write_bundle_tree(path: Path, *, marker: str) -> None:
    """Write one extracted Windows launcher bundle."""

    path.mkdir(parents=True)
    (path / "SugarSubstitute.exe").write_text(marker, encoding="utf-8")
    (path / "launcher-bin").mkdir()
    (path / "launcher-bin" / "runtime.txt").write_text("new", encoding="utf-8")


def _asset(path: Path) -> LauncherBundleAsset:
    """Create a manifest asset for one local test archive."""

    return LauncherBundleAsset(
        filename=path.name,
        url=path.resolve().as_uri(),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        size_bytes=path.stat().st_size,
    )


def _manifest_payload(archive: Path) -> dict[str, object]:
    """Create the launcher portion of a production manifest."""

    asset = _asset(archive)
    return {
        "schema_version": 2,
        "channel": "stable",
        "version": "0.11.0",
        "minimum_launcher_version": "0.10.0",
        "launchers": {
            "windows_x64": {
                "filename": asset.filename,
                "url": asset.url,
                "sha256": asset.sha256,
                "size_bytes": asset.size_bytes,
            }
        },
    }


def _write_launcher_config(root: Path, *, runtime_python: Path) -> None:
    """Write the installed config fields consumed by the legacy bridge."""

    config_path = root / "launcher" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "install_root": str(root),
                "app_dir": str(root / "app"),
                "runtime_python": str(runtime_python),
                "channel": "stable",
                "update_check": {"enabled": True, "frequency": "daily"},
                "release_source": {
                    "kind": "github_release_manifest",
                    "manifest_url": "https://example.test/manifest.json",
                },
            }
        ),
        encoding="utf-8",
    )
