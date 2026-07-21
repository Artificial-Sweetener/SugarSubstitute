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

"""Provision and verify the launcher-managed Python runtime."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from launcher.sugarsubstitute_launcher.downloader import AssetDownloader
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset
from launcher.sugarsubstitute_launcher.payload import (
    safe_extract_tar_gzip,
    safe_extract_zip,
)
from launcher.sugarsubstitute_launcher.platforms import (
    LauncherOperatingSystem,
    LauncherTarget,
)
from sugarsubstitute_shared.windows_long_paths import (
    external_long_path_error,
    operational_path,
    subprocess_path,
    subprocess_working_directory,
)


_LOGGER = logging.getLogger(__name__)
_FAILURE_OUTPUT_LOG_LINE_LIMIT = 200
_BASIC_AUTH_URL_PATTERN = re.compile(r"(?i)\b(https?://)[^/\s:@]+:[^@\s/]+@")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|secret|token)=([^\s&]+)"
)
_BEARER_TOKEN_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s]+")
DEFAULT_PYTHON_VERSION = "3.13.12"
CRITICAL_IMPORTS: tuple[str, ...] = (
    "PySide6",
    "qfluentwidgets",
    "qpane",
    "substitute",
)


class RuntimeProvisioningError(RuntimeError):
    """Raised when the launcher-managed Python runtime cannot be prepared."""


class RuntimeCommandRunner(Protocol):
    """Run one runtime provisioning subprocess command."""

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> None:
        """Run one command or raise on failure."""


@dataclass(frozen=True, slots=True)
class RuntimeProvisioningResult:
    """Describe a provisioned launcher-managed runtime."""

    python_executable: Path
    requirements_path: Path


class SubprocessRuntimeCommandRunner:
    """Run runtime commands through subprocess without shell execution."""

    def __init__(self, output_callback: Callable[[str], None] | None = None) -> None:
        """Store the optional output sink used by graphical installers."""

        self._output_callback = output_callback

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> None:
        """Run one subprocess command and preserve failure context."""

        executable_name = Path(command[0]).name if command else ""
        _LOGGER.info(
            "Starting runtime command | executable=%s argument_count=%d cwd=%s",
            executable_name,
            len(command),
            cwd,
        )
        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = subprocess.CREATE_NO_WINDOW

        process_cwd = operational_path(cwd)
        try:
            process = subprocess.Popen(  # noqa: S603
                list(command),
                cwd=subprocess_working_directory(process_cwd),
                env=dict(env),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                shell=False,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
        except OSError as error:
            compatibility_error = external_long_path_error(
                component=executable_name,
                path=process_cwd,
                detail=error,
            )
            if compatibility_error is not None:
                raise compatibility_error from error
            raise
        captured_output: list[str] = []
        if process.stdout is not None:
            for raw_line in process.stdout:
                line = _decode_process_output_line(raw_line)
                if line:
                    captured_output.append(line)
                    if self._output_callback is not None:
                        self._output_callback(line)

        return_code = process.wait()
        if return_code != 0:
            detail = "\n".join(captured_output)
            compatibility_error = external_long_path_error(
                component=executable_name,
                path=process_cwd,
                detail=detail,
            )
            if compatibility_error is not None:
                raise compatibility_error
            for line in captured_output[-_FAILURE_OUTPUT_LOG_LINE_LIMIT:]:
                _LOGGER.error(
                    "Runtime command failure output | executable=%s output=%s",
                    executable_name,
                    _sanitize_runtime_log_line(line),
                )
            _LOGGER.error(
                "Runtime command failed | executable=%s return_code=%d output_line_count=%d",
                executable_name,
                return_code,
                len(captured_output),
            )
            raise subprocess.CalledProcessError(
                return_code,
                list(command),
                output="\n".join(captured_output),
            )
        _LOGGER.info(
            "Runtime command completed | executable=%s return_code=0 output_line_count=%d",
            executable_name,
            len(captured_output),
        )


def _sanitize_runtime_log_line(line: str) -> str:
    """Redact common credential forms before persisting subprocess output."""

    sanitized = _BASIC_AUTH_URL_PATTERN.sub(r"\1<redacted>@", line)
    sanitized = _SECRET_ASSIGNMENT_PATTERN.sub(r"\1=<redacted>", sanitized)
    return _BEARER_TOKEN_PATTERN.sub("Bearer <redacted>", sanitized)


class UvManagedRuntimeInstaller:
    """Install Python, create the app venv, and install app requirements."""

    def __init__(
        self,
        *,
        python_version: str = DEFAULT_PYTHON_VERSION,
        bundled_uv_path: Path | None = None,
        uv_archive_asset: ReleaseAsset | None = None,
        downloader: AssetDownloader | None = None,
        runner: RuntimeCommandRunner | None = None,
    ) -> None:
        """Store the uv and subprocess collaborators used for provisioning."""

        self._python_version = python_version
        self._bundled_uv_path = bundled_uv_path
        self._uv_archive_asset = uv_archive_asset
        self._downloader = downloader or AssetDownloader()
        self._runner = runner or SubprocessRuntimeCommandRunner()

    def provision(self, *, layout: InstallLayout) -> RuntimeProvisioningResult:
        """Ensure the launcher-managed runtime can run the installed app."""

        layout.create_base_directories()
        requirements_path = layout.app_dir / "requirements.txt"
        if not requirements_path.is_file():
            raise RuntimeProvisioningError(
                f"Requirements file is missing: {requirements_path}"
            )

        uv_executable = self.ensure_uv(layout=layout)
        env = runtime_environment(layout=layout)
        python_install_command = [
            subprocess_path(uv_executable),
            "python",
            "install",
            self._python_version,
            "--install-dir",
            subprocess_path(layout.runtime_dir / "python"),
            "--managed-python",
            "--no-bin",
            "--no-config",
        ]
        if layout.target.operating_system is LauncherOperatingSystem.WINDOWS:
            python_install_command.insert(-1, "--no-registry")
        self._runner.run(
            python_install_command,
            cwd=layout.root,
            env=env,
        )
        venv_path = layout.runtime_dir / ".venv"
        if not _managed_venv_matches(
            layout=layout,
            python_version=self._python_version,
        ):
            venv_command = [
                subprocess_path(uv_executable),
                "venv",
                subprocess_path(venv_path),
                "--python",
                self._python_version,
                "--managed-python",
                "--no-config",
            ]
            if venv_path.exists():
                venv_command.append("--clear")
            self._runner.run(
                venv_command,
                cwd=layout.root,
                env=env,
            )
        self._runner.run(
            runtime_requirements_command(
                uv_executable=uv_executable,
                layout=layout,
                requirements_path=requirements_path,
            ),
            cwd=layout.root,
            env=env,
        )
        verify_runtime_imports(
            python_executable=layout.runtime_python,
            imports=CRITICAL_IMPORTS,
            runner=self._runner,
            cwd=layout.root,
            env=env,
        )
        return RuntimeProvisioningResult(
            python_executable=layout.runtime_python,
            requirements_path=requirements_path,
        )

    def ensure_uv(self, *, layout: InstallLayout) -> Path:
        """Ensure the standalone uv executable exists under runtime tools."""

        uv_executable = layout.uv_executable
        if uv_executable.is_file():
            return uv_executable
        if self._bundled_uv_path is not None:
            return _copy_uv_executable(
                source_path=self._bundled_uv_path,
                destination_path=uv_executable,
            )
        if self._uv_archive_asset is None:
            raise RuntimeProvisioningError(
                f"{layout.target.uv_executable_name} is missing and no bundled uv "
                "executable or verified uv archive is configured."
            )

        archive_path = layout.downloads_dir / "uv" / self._uv_archive_asset.filename
        self._downloader.download(
            asset=self._uv_archive_asset, destination_path=archive_path
        )
        _verify_file_sha256(
            path=archive_path, expected_sha256=self._uv_archive_asset.sha256
        )
        extracted_dir = layout.runtime_dir / "uv_extract"
        if extracted_dir.exists():
            shutil.rmtree(extracted_dir)
        _extract_uv_archive(archive_path=archive_path, destination_dir=extracted_dir)
        extracted_uv = _find_uv_executable(
            extracted_dir,
            executable_name=layout.target.uv_executable_name,
        )
        uv_executable.parent.mkdir(parents=True, exist_ok=True)
        _copy_uv_executable(
            source_path=extracted_uv,
            destination_path=uv_executable,
        )
        shutil.rmtree(extracted_dir)
        return uv_executable


def runtime_requirements_command(
    *,
    uv_executable: Path,
    layout: InstallLayout,
    requirements_path: Path,
) -> list[str]:
    """Build the target-specific uv command for app runtime dependencies."""

    command = [
        subprocess_path(uv_executable),
        "pip",
        "install",
        "--python",
        subprocess_path(layout.runtime_python),
    ]
    command.extend(_torch_backend_arguments(layout.target))
    command.extend(["-r", subprocess_path(requirements_path)])
    return command


def _torch_backend_arguments(target: LauncherTarget) -> list[str]:
    """Select a portable PyTorch distribution for the app support runtime."""

    if target.operating_system is LauncherOperatingSystem.LINUX:
        return ["--torch-backend", "cpu"]
    return []


def runtime_environment(*, layout: InstallLayout) -> dict[str, str]:
    """Build the environment that keeps uv and Python state deterministic."""

    env = dict(os.environ)
    env["UV_CACHE_DIR"] = subprocess_path(layout.cache_dir / "uv")
    env["UV_PYTHON_INSTALL_DIR"] = subprocess_path(layout.runtime_dir / "python")
    env["UV_NO_MODIFY_PATH"] = "1"
    env["VIRTUAL_ENV"] = subprocess_path(layout.runtime_dir / ".venv")
    env["PYTHONPATH"] = subprocess_path(layout.app_dir)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    return env


def _decode_process_output_line(raw_line: bytes) -> str:
    """Decode one subprocess output line without depending on Windows code pages."""

    return raw_line.decode("utf-8", errors="replace").rstrip()


def _managed_venv_matches(
    *,
    layout: InstallLayout,
    python_version: str,
) -> bool:
    """Return whether the existing managed venv already uses the pinned Python."""

    if not layout.runtime_python.is_file():
        return False
    config_path = layout.runtime_dir / ".venv" / "pyvenv.cfg"
    try:
        config_lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    config = {
        key.strip().casefold(): value.strip()
        for line in config_lines
        if "=" in line
        for key, value in (line.split("=", maxsplit=1),)
    }
    return (
        config.get("implementation", "").casefold() == "cpython"
        and config.get("version_info") == python_version
    )


def verify_runtime_imports(
    *,
    python_executable: Path,
    imports: Sequence[str],
    runner: RuntimeCommandRunner,
    cwd: Path,
    env: Mapping[str, str],
) -> None:
    """Verify that the managed runtime can import critical packages."""

    import_statement = "; ".join(f"import {module_name}" for module_name in imports)
    runner.run(
        [subprocess_path(python_executable), "-c", import_statement],
        cwd=cwd,
        env=env,
    )


def _find_uv_executable(extracted_dir: Path, *, executable_name: str) -> Path:
    """Find the target uv executable inside a safely extracted release archive."""

    matches = [path for path in extracted_dir.rglob(executable_name) if path.is_file()]
    if not matches:
        raise RuntimeProvisioningError(
            f"Downloaded uv archive does not contain {executable_name}: {extracted_dir}"
        )
    return matches[0]


def _copy_uv_executable(*, source_path: Path, destination_path: Path) -> Path:
    """Copy a bundled uv executable into the launcher-managed runtime."""

    if not source_path.is_file():
        raise RuntimeProvisioningError(
            f"Bundled uv executable is missing: {source_path}"
        )
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)
    destination_path.chmod(destination_path.stat().st_mode | 0o111)
    return destination_path


def _extract_uv_archive(*, archive_path: Path, destination_dir: Path) -> None:
    """Extract one supported official uv release archive safely."""

    if archive_path.name.endswith(".zip"):
        safe_extract_zip(zip_path=archive_path, destination_dir=destination_dir)
        return
    if archive_path.name.endswith((".tar.gz", ".tgz")):
        safe_extract_tar_gzip(tar_path=archive_path, destination_dir=destination_dir)
        return
    raise RuntimeProvisioningError(
        f"Unsupported uv archive format: {archive_path.name}"
    )


def _verify_file_sha256(*, path: Path, expected_sha256: str) -> None:
    """Verify a downloaded uv archive before extracting it."""

    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().lower() != expected_sha256.lower():
        raise RuntimeProvisioningError(f"uv archive SHA256 mismatch: {path}")
