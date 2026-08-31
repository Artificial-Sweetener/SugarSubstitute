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

"""Build the pinned Crashpad handler and SugarSubstitute client bridge."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


CRASHPAD_REVISION = "60dd943f48d77dc8d05dabc04badbd8561d0b8c4"
CRASHPAD_SOURCE_URL = "https://chromium.googlesource.com/crashpad/crashpad.git"
DEPOT_TOOLS_URL = "https://chromium.googlesource.com/chromium/tools/depot_tools.git"
_OVERLAY_MARKER = "# SugarSubstitute native Crashpad bridge"


@dataclass(frozen=True, slots=True)
class CrashpadRuntimeTarget:
    """Name the build and packaging contract for one official platform."""

    directory_name: str
    target_cpu: str
    handler_name: str
    client_name: str


def main(argv: list[str] | None = None) -> int:
    """Fetch, build, and stage the native runtime for the current platform."""

    arguments = _parse_arguments(argv)
    target = _platform_target()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = arguments.workspace.expanduser().resolve()
    depot_tools = workspace / "depot_tools"
    checkout_root = workspace / "checkout"
    crashpad = checkout_root / "crashpad"
    _clone_if_missing(DEPOT_TOOLS_URL, depot_tools)
    _clone_if_missing(CRASHPAD_SOURCE_URL, crashpad)
    _remove_owned_overlay(crashpad)
    _run(["git", "checkout", "--detach", CRASHPAD_REVISION], cwd=crashpad)
    _write_gclient(checkout_root)
    environment = _build_environment(depot_tools)
    _run_tool(
        depot_tools / _tool_name("gclient"),
        ["sync", "--nohooks", "--revision", f"crashpad@{CRASHPAD_REVISION}"],
        cwd=checkout_root,
        environment=environment,
    )
    _configure_windows_toolchain_selection(crashpad)
    _verify_revision(crashpad)
    _install_overlay(repo_root=repo_root, crashpad=crashpad)
    output_directory = crashpad / "out" / "SugarSubstitute"
    _write_gn_arguments(output_directory, target_cpu=target.target_cpu)
    _run_tool(
        depot_tools / _tool_name("gn"),
        ["gen", str(output_directory)],
        cwd=crashpad,
        environment=environment,
    )
    targets = ["crashpad_handler", "sugarsubstitute_native"]
    if arguments.with_probe:
        targets.append("sugarsubstitute_crashpad_probe")
    _run(
        [
            str(_ninja_executable(crashpad, depot_tools)),
            "-C",
            str(output_directory),
            *targets,
        ],
        cwd=crashpad,
        environment=environment,
    )
    staged = _stage_runtime(
        output_directory=output_directory,
        output_root=arguments.output_root.expanduser().resolve(),
        target=target,
    )
    for path in staged:
        print(f"{path.name} sha256={_sha256(path)}")
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    """Parse explicit build and staging paths."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("third_party") / "bin" / "crashpad",
    )
    parser.add_argument("--with-probe", action="store_true")
    return parser.parse_args(argv)


def _clone_if_missing(url: str, destination: Path) -> None:
    """Create one source checkout without mutating an existing clone."""

    if (destination / ".git").is_dir():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "clone", url, str(destination)], cwd=destination.parent)


def _write_gclient(checkout_root: Path) -> None:
    """Write the pinned Crashpad dependency solution consumed by gclient."""

    checkout_root.mkdir(parents=True, exist_ok=True)
    (checkout_root / ".gclient").write_text(
        "solutions = [{\n"
        "  'name': 'crashpad',\n"
        f"  'url': '{CRASHPAD_SOURCE_URL}',\n"
        "  'managed': False,\n"
        "}]\n",
        encoding="utf-8",
    )


def _remove_owned_overlay(crashpad: Path) -> None:
    """Restore only files this build tool modifies before dependency sync."""

    _run(["git", "restore", "--source=HEAD", "--", "BUILD.gn"], cwd=crashpad)
    overlay = crashpad / "sugarsubstitute"
    if overlay.is_dir():
        shutil.rmtree(overlay)
    win_helper = (
        crashpad
        / "third_party"
        / "mini_chromium"
        / "mini_chromium"
        / "build"
        / "win_helper.py"
    )
    if (win_helper.parent.parent / ".git").is_dir() or win_helper.is_file():
        mini_chromium = crashpad / "third_party" / "mini_chromium" / "mini_chromium"
        if (mini_chromium / ".git").is_dir() or (mini_chromium / ".git").is_file():
            _run(
                ["git", "restore", "--source=HEAD", "--", "build/win_helper.py"],
                cwd=mini_chromium,
            )


def _configure_windows_toolchain_selection(crashpad: Path) -> None:
    """Require a Visual Studio installation with the native C++ workload."""

    if sys.platform != "win32":
        return
    helper = (
        crashpad
        / "third_party"
        / "mini_chromium"
        / "mini_chromium"
        / "build"
        / "win_helper.py"
    )
    content = helper.read_text(encoding="utf-8")
    original = (
        "vswhere_path, '-products', '*', '-latest', '-property',\n"
        "                    'installationPath'"
    )
    replacement = (
        "vswhere_path, '-products', '*', '-latest', '-requires',\n"
        "                    'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',\n"
        "                    '-property', 'installationPath'"
    )
    if original in content:
        helper.write_text(content.replace(original, replacement), encoding="utf-8")


def _build_environment(depot_tools: Path) -> dict[str, str]:
    """Return an isolated tool environment using the host compiler."""

    environment = dict(os.environ)
    environment["PATH"] = f"{depot_tools}{os.pathsep}{environment.get('PATH', '')}"
    if sys.platform == "win32":
        environment["DEPOT_TOOLS_WIN_TOOLCHAIN"] = "0"
    return environment


def _install_overlay(*, repo_root: Path, crashpad: Path) -> None:
    """Install authored bridge sources and one reachable GN aggregation target."""

    source = repo_root / "native" / "crashpad"
    destination = crashpad / "sugarsubstitute"
    destination.mkdir(parents=True, exist_ok=True)
    for filename in (
        "BUILD.gn",
        "crashpad_client_bridge.cc",
        "crashpad_native_probe.cc",
    ):
        shutil.copy2(source / filename, destination / filename)
    root_build = crashpad / "BUILD.gn"
    content = root_build.read_text(encoding="utf-8")
    if _OVERLAY_MARKER in content:
        return
    root_build.write_text(
        content
        + "\n"
        + _OVERLAY_MARKER
        + "\n"
        + 'group("sugarsubstitute_native") {\n'
        + '  deps = [ "//sugarsubstitute:sugarsubstitute_crashpad_client" ]\n'
        + "}\n",
        encoding="utf-8",
    )


def _write_gn_arguments(output_directory: Path, *, target_cpu: str) -> None:
    """Configure a release build for the current official architecture."""

    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "args.gn").write_text(
        f'is_debug = false\ntarget_cpu = "{target_cpu}"\n',
        encoding="utf-8",
    )


def _verify_revision(crashpad: Path) -> None:
    """Reject source drift before compiling release binaries."""

    result = _run(
        ["git", "rev-parse", "HEAD"],
        cwd=crashpad,
        capture_output=True,
    )
    if result.stdout.strip() != CRASHPAD_REVISION:
        raise RuntimeError("Crashpad checkout does not match the pinned revision.")


def _stage_runtime(
    *,
    output_directory: Path,
    output_root: Path,
    target: CrashpadRuntimeTarget,
) -> tuple[Path, Path]:
    """Copy the platform handler and client library into packaging inputs."""

    destination = output_root / target.directory_name
    destination.mkdir(parents=True, exist_ok=True)
    handler = destination / target.handler_name
    client = destination / target.client_name
    shutil.copy2(output_directory / target.handler_name, handler)
    shutil.copy2(output_directory / target.client_name, client)
    return handler, client


def _platform_target(
    *,
    platform_name: str | None = None,
    machine: str | None = None,
) -> CrashpadRuntimeTarget:
    """Return the exact native contract for one supported release host."""

    resolved_platform = platform_name or sys.platform
    resolved_machine = (machine or platform.machine()).strip().lower()
    if resolved_platform == "win32" and resolved_machine in {"amd64", "x86_64"}:
        return CrashpadRuntimeTarget(
            directory_name="windows-x64",
            target_cpu="x64",
            handler_name="crashpad_handler.exe",
            client_name="sugarsubstitute_crashpad_client.dll",
        )
    if resolved_platform == "darwin" and resolved_machine in {"arm64", "aarch64"}:
        return CrashpadRuntimeTarget(
            directory_name="macos-arm64",
            target_cpu="arm64",
            handler_name="crashpad_handler",
            client_name="sugarsubstitute_crashpad_client.dylib",
        )
    if resolved_platform.startswith("linux") and resolved_machine in {
        "amd64",
        "x86_64",
    }:
        return CrashpadRuntimeTarget(
            directory_name="linux-x64",
            target_cpu="x64",
            handler_name="crashpad_handler",
            client_name="sugarsubstitute_crashpad_client.so",
        )
    raise RuntimeError(
        "Unsupported Crashpad release platform: "
        f"{resolved_platform}/{machine or platform.machine()}"
    )


def _tool_name(name: str) -> str:
    """Return a directly invocable depot_tools wrapper name."""

    return f"{name}.bat" if sys.platform == "win32" else name


def _run_tool(
    tool: Path,
    arguments: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
) -> None:
    """Run one depot_tools wrapper on scripts and native hosts."""

    command = [str(tool), *arguments]
    if sys.platform == "win32" and tool.suffix.casefold() == ".bat":
        command = ["cmd.exe", "/d", "/c", *command]
    _run(command, cwd=cwd, environment=environment)


def _ninja_executable(crashpad: Path, depot_tools: Path) -> Path:
    """Return the synchronized Ninja executable for this host."""

    executable = "ninja.exe" if sys.platform == "win32" else "ninja"
    synchronized = crashpad / "third_party" / "ninja" / executable
    return synchronized if synchronized.is_file() else depot_tools / executable


def _run(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run one checked build command without shell interpretation."""

    return subprocess.run(  # noqa: S603
        command,
        cwd=cwd,
        env=environment,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def _sha256(path: Path) -> str:
    """Return a release-audit digest for one staged binary."""

    digest = hashlib.sha256()
    with path.open("rb") as binary:
        for chunk in iter(lambda: binary.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
