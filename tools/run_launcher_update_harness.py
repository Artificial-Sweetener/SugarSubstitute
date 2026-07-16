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

"""Exercise a real detached legacy-to-self-updating launcher transition."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from substitute.infrastructure.launcher_update.legacy_bridge import (  # noqa: E402
    LegacyLauncherUpdateBridge,
)
from sugarsubstitute_shared.launcher_update.models import (  # noqa: E402
    LauncherBundleAsset,
    LauncherInstallationRecord,
)
from sugarsubstitute_shared.launcher_update.process import (  # noqa: E402
    schedule_launcher_update,
)
from sugarsubstitute_shared.launcher_update.staging import (  # noqa: E402
    LauncherBundleStager,
)
from sugarsubstitute_shared.launcher_update.targets import (  # noqa: E402
    WINDOWS_X64_BUNDLE,
)


HARNESS_VERSION = "99.0.0"


def main() -> int:
    """Build a probe launcher, replace it detached, and prove uv stays local."""

    repo_root = Path(__file__).resolve().parents[1]
    harness_root = repo_root / ".tmp" / "launcher-update-harness"
    _reset_harness_root(harness_root=harness_root, repo_root=repo_root)
    install_root = harness_root / "SugarSubstitute"
    build_root = harness_root / "build"
    _create_old_install(install_root=install_root, repo_root=repo_root)
    bundle_path = _build_probe_bundle(
        build_root=build_root,
        output_path=harness_root / "launcher.zip",
        repo_python=Path(sys.executable),
    )
    asset = LauncherBundleAsset(
        filename=bundle_path.name,
        url=bundle_path.as_uri(),
        sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
        size_bytes=bundle_path.stat().st_size,
    )
    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version=HARNESS_VERSION,
        target=WINDOWS_X64_BUNDLE,
        asset=asset,
    )
    runtime_python = install_root / "runtime" / ".venv" / "Scripts" / "python.exe"
    blocker = subprocess.Popen(  # noqa: S603
        [str(runtime_python), "-c", "import time; time.sleep(30)"],
        cwd=install_root,
    )
    helper_pid = schedule_launcher_update(
        request_path=request_path,
        runtime_python=runtime_python,
        app_dir=install_root / "app",
        relaunch=True,
        wait_pid=blocker.pid,
    )
    marker_path = install_root / "launcher-relaunched.json"
    time.sleep(0.5)
    if marker_path.exists() or blocker.poll() is not None:
        raise RuntimeError("Launcher helper did not safely wait for its owner process.")
    blocker.terminate()
    blocker.wait(timeout=10.0)
    _wait_for_path(marker_path, timeout_seconds=45.0)
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("executable") != str(install_root / "SugarSubstitute.exe"):
        raise RuntimeError(f"Updated launcher ran from an unexpected path: {marker}")
    record = LauncherInstallationRecord.load(
        install_root / "launcher" / "installation.json"
    )
    if record != LauncherInstallationRecord(
        version=HARNESS_VERSION,
        target_key="windows_x64",
    ):
        raise RuntimeError(f"Launcher installation record is wrong: {record}")
    _assert_preserved_install_data(install_root)
    _assert_bridge_is_now_a_noop(install_root=install_root, asset=asset)
    _prove_uv_does_not_write_global_shims(
        harness_root=harness_root,
        uv_executable=repo_root / ".venv" / "Scripts" / "uv.exe",
    )
    print(
        "Launcher update harness passed: "
        f"helper_pid={helper_pid}, install_root={install_root}"
    )
    return 0


def _reset_harness_root(*, harness_root: Path, repo_root: Path) -> None:
    """Clean only the named disposable directory inside this repository."""

    resolved = harness_root.resolve()
    expected_parent = (repo_root / ".tmp").resolve()
    if resolved.parent != expected_parent or resolved.name != "launcher-update-harness":
        raise RuntimeError(f"Refusing to clean unexpected harness path: {resolved}")
    shutil.rmtree(resolved, ignore_errors=True)
    resolved.mkdir(parents=True)


def _create_old_install(*, install_root: Path, repo_root: Path) -> None:
    """Create a release-shaped legacy install with a real managed Python venv."""

    install_root.mkdir(parents=True)
    (install_root / "SugarSubstitute.exe").write_bytes(b"legacy launcher")
    (install_root / "launcher-bin").mkdir()
    (install_root / "launcher-bin" / "legacy.txt").write_text(
        "legacy", encoding="utf-8"
    )
    app_dir = install_root / "app"
    shutil.copytree(
        repo_root / "sugarsubstitute_shared", app_dir / "sugarsubstitute_shared"
    )
    (app_dir / "main.py").write_text("# harness app\n", encoding="utf-8")
    subprocess.run(
        [
            str(repo_root / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "venv",
            str(install_root / "runtime" / ".venv"),
        ],
        check=True,
        cwd=repo_root,
    )
    for relative_path in (
        "app/preserve.txt",
        "runtime/preserve.txt",
        "comfyui/preserve.txt",
        "user/preserve.txt",
        "appdata/preserve.txt",
    ):
        path = install_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("preserved", encoding="utf-8")
    config_path = install_root / "launcher" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "install_root": str(install_root),
                "app_dir": str(app_dir),
                "runtime_python": str(
                    install_root / "runtime" / ".venv" / "Scripts" / "python.exe"
                ),
                "channel": "stable",
                "update_check": {"enabled": True, "frequency": "daily"},
                "release_source": {
                    "kind": "github_release_manifest",
                    "manifest_url": "https://example.test/manifest.json",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _build_probe_bundle(
    *,
    build_root: Path,
    output_path: Path,
    repo_python: Path,
) -> Path:
    """Build a real onedir executable that records detached relaunch success."""

    script_path = build_root / "probe_launcher.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text(
        "\n".join(
            (
                "import json",
                "from pathlib import Path",
                "import sys",
                "root = Path(sys.executable).resolve().parent",
                "(root / 'launcher-relaunched.json').write_text(",
                "    json.dumps({'executable': str(Path(sys.executable).resolve())}),",
                "    encoding='utf-8',",
                ")",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            str(repo_python),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--contents-directory",
            "launcher-bin",
            "--name",
            "SugarSubstitute",
            "--distpath",
            str(build_root / "dist"),
            "--workpath",
            str(build_root / "work"),
            "--specpath",
            str(build_root),
            str(script_path),
        ],
        check=True,
        cwd=build_root,
        stdout=subprocess.DEVNULL,
    )
    bundle_dir = build_root / "dist" / "SugarSubstitute"
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(bundle_dir).as_posix())
    return output_path


def _wait_for_path(path: Path, *, timeout_seconds: float) -> None:
    """Wait for the relaunched probe to write its observable marker."""

    deadline = time.monotonic() + timeout_seconds
    while not path.is_file():
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for updated launcher: {path}")
        time.sleep(0.1)


def _assert_preserved_install_data(install_root: Path) -> None:
    """Prove replacement did not touch any non-launcher install ownership."""

    for relative_path in (
        "app/preserve.txt",
        "runtime/preserve.txt",
        "comfyui/preserve.txt",
        "user/preserve.txt",
        "appdata/preserve.txt",
    ):
        if (install_root / relative_path).read_text(encoding="utf-8") != "preserved":
            raise RuntimeError(
                f"Launcher update changed preserved data: {relative_path}"
            )


def _assert_bridge_is_now_a_noop(
    *,
    install_root: Path,
    asset: LauncherBundleAsset,
) -> None:
    """Prove the one-time app bridge yields to the updated launcher record."""

    payload = {
        "schema_version": 2,
        "channel": "stable",
        "version": HARNESS_VERSION,
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
    bridge = LegacyLauncherUpdateBridge(
        target_detector=lambda: WINDOWS_X64_BUNDLE,
        manifest_loader=lambda _url: payload,
        scheduler=lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("Current launcher must not be rescheduled.")
        ),
    )
    if bridge.run(install_root=install_root):
        raise RuntimeError("Current launcher was incorrectly scheduled again.")


def _prove_uv_does_not_write_global_shims(
    *,
    harness_root: Path,
    uv_executable: Path,
) -> None:
    """Run real uv with the fixed flags and prove its bin target stays untouched."""

    fake_home = harness_root / "isolated-home"
    bin_dir = fake_home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    sentinel = bin_dir / "python3.13.exe"
    sentinel.write_text("unmanaged sentinel", encoding="utf-8")
    environment = os.environ.copy()
    environment["HOME"] = str(fake_home)
    environment["USERPROFILE"] = str(fake_home)
    environment["UV_PYTHON_BIN_DIR"] = str(bin_dir)
    environment["UV_CACHE_DIR"] = str(harness_root / "uv-cache")
    subprocess.run(
        [
            str(uv_executable),
            "python",
            "install",
            "3.13.12",
            "--install-dir",
            str(harness_root / "uv-python"),
            "--managed-python",
            "--no-bin",
            "--no-registry",
            "--no-config",
        ],
        check=True,
        cwd=harness_root,
        env=environment,
    )
    if sentinel.read_text(encoding="utf-8") != "unmanaged sentinel":
        raise RuntimeError("uv replaced an unmanaged global Python shim.")
    if list(bin_dir.iterdir()) != [sentinel]:
        raise RuntimeError("uv wrote unexpected global Python shims.")


if __name__ == "__main__":
    raise SystemExit(main())
