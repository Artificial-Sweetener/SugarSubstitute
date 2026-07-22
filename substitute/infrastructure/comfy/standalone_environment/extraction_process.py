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

"""Run standalone 7z work in a responsive native process boundary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import time
from typing import Protocol

from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArtifactError,
)
from substitute.infrastructure.execution.process_output import BinaryProcessOutput
from sugarsubstitute_shared.windows_long_paths import (
    external_long_path_error,
    operational_path,
    subprocess_path,
    subprocess_working_directory,
)


_LOGGER = logging.getLogger(__name__)
_DEFAULT_EXTRACTION_TIMEOUT_SECONDS = 7_200.0
_LISTING_TIMEOUT_SECONDS = 300.0
_OUTPUT_TAIL_LIMIT = 20_000
_PERCENTAGE_PATTERN = re.compile(r"(?<!\d)(\d{1,3})%")


@dataclass(frozen=True, slots=True)
class SevenZipExtractionProgress:
    """Describe native extraction progress and its estimated remaining time."""

    percentage: int
    elapsed_seconds: float
    estimated_remaining_seconds: float | None


SevenZipProgressCallback = Callable[[SevenZipExtractionProgress], None]


class SevenZipExtractionProcess(Protocol):
    """List and extract one 7z archive across a native process boundary."""

    def list_members(self, archive_path: Path) -> tuple[str, ...]:
        """Return validated-input member names without extracting content."""

    def extract(
        self,
        archive_path: Path,
        destination: Path,
        *,
        on_progress: SevenZipProgressCallback | None = None,
    ) -> None:
        """Extract the archive into the existing destination directory."""


class NativeSevenZipExtractionProcess:
    """Use the bundled native 7-Zip binary without contending for Python's GIL."""

    def __init__(
        self,
        *,
        executable_path: Path | None = None,
        application_root: Path | None = None,
        timeout_seconds: float = _DEFAULT_EXTRACTION_TIMEOUT_SECONDS,
    ) -> None:
        """Resolve the platform binary and store a bounded extraction timeout."""

        if timeout_seconds <= 0:
            raise ValueError("Extraction timeout must be positive.")
        root = application_root or Path(__file__).resolve().parents[4]
        self._executable_path = executable_path or bundled_seven_zip_path(root)
        self._timeout_seconds = timeout_seconds

    def list_members(self, archive_path: Path) -> tuple[str, ...]:
        """List members through native 7-Zip for multipart-aware validation."""

        executable = self._prepared_executable()
        completed = _run_bounded(
            (
                subprocess_path(executable),
                "l",
                "-slt",
                subprocess_path(archive_path),
            ),
            cwd=archive_path.parent,
            timeout_seconds=min(self._timeout_seconds, _LISTING_TIMEOUT_SECONDS),
        )
        if completed.returncode != 0:
            self._raise_failed_process(
                operation="listing",
                archive_path=archive_path,
                compatibility_path=archive_path,
                return_code=completed.returncode,
                output=completed.stdout,
            )
        members = _parse_member_paths(completed.stdout)
        if not members:
            raise StandaloneArtifactError(
                f"Native 7-Zip found no members in {archive_path.name}."
            )
        return members

    def extract(
        self,
        archive_path: Path,
        destination: Path,
        *,
        on_progress: SevenZipProgressCallback | None = None,
    ) -> None:
        """Extract natively while streaming percentage progress to the caller."""

        executable = self._prepared_executable()
        command = (
            subprocess_path(executable),
            "x",
            subprocess_path(archive_path),
            f"-o{subprocess_path(destination)}",
            "-y",
            "-bsp1",
        )
        startupinfo, creationflags = _hidden_process_options()
        _LOGGER.info(
            "Starting native standalone extraction | archive_name=%s",
            archive_path.name,
        )
        try:
            process = subprocess.Popen(  # noqa: S603
                command,
                cwd=subprocess_working_directory(archive_path.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
        except OSError as error:
            compatibility_error = external_long_path_error(
                component="7-Zip",
                path=destination,
                detail=error,
            )
            if compatibility_error is not None:
                raise compatibility_error from error
            raise StandaloneArtifactError(
                "Could not start the bundled native 7-Zip process."
            ) from error

        process_output = BinaryProcessOutput(process)
        started_at = time.monotonic()
        output_tail = ""
        percentage_tail = ""
        last_percentage = -1
        try:
            while process.poll() is None:
                chunk = process_output.take()
                if chunk is not None:
                    decoded = chunk.decode("utf-8", errors="replace")
                    output_tail = (output_tail + decoded)[-_OUTPUT_TAIL_LIMIT:]
                    percentage_tail, last_percentage = _publish_percentages(
                        percentage_tail + decoded,
                        started_at=started_at,
                        previous_percentage=last_percentage,
                        callback=on_progress,
                    )
                if time.monotonic() - started_at > self._timeout_seconds:
                    process.kill()
                    process.wait(timeout=30)
                    raise StandaloneArtifactError(
                        "Native standalone 7-Zip extraction timed out."
                    )
        finally:
            process_output.join()

        while True:
            chunk = process_output.take(wait_seconds=0.0)
            if chunk is None:
                break
            decoded = chunk.decode("utf-8", errors="replace")
            output_tail = (output_tail + decoded)[-_OUTPUT_TAIL_LIMIT:]
            percentage_tail, last_percentage = _publish_percentages(
                percentage_tail + decoded,
                started_at=started_at,
                previous_percentage=last_percentage,
                callback=on_progress,
            )

        return_code = process.returncode
        if return_code != 0:
            self._raise_failed_process(
                operation="extraction",
                archive_path=archive_path,
                compatibility_path=destination,
                return_code=return_code,
                output=output_tail,
            )
        if last_percentage < 100:
            _publish_progress(
                percentage=100,
                started_at=started_at,
                callback=on_progress,
            )
        _LOGGER.info(
            "Native standalone extraction completed | archive_name=%s "
            "elapsed_seconds=%.3f",
            archive_path.name,
            time.monotonic() - started_at,
        )

    def _prepared_executable(self) -> Path:
        """Require the bundled binary and make Unix payloads executable."""

        executable = operational_path(self._executable_path).resolve()
        if not executable.is_file():
            raise StandaloneArtifactError(
                f"Bundled native 7-Zip binary is missing: {executable}"
            )
        if sys.platform != "win32":
            executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        return executable

    @staticmethod
    def _raise_failed_process(
        *,
        operation: str,
        archive_path: Path,
        compatibility_path: Path,
        return_code: int,
        output: str | None,
    ) -> None:
        """Raise one actionable bounded native-process error."""

        detail = _tail_output(output)
        _LOGGER.error(
            "Native standalone 7-Zip %s failed | archive_name=%s "
            "return_code=%d output=%s",
            operation,
            archive_path.name,
            return_code,
            detail,
        )
        suffix = f" Details: {detail}" if detail else ""
        compatibility_error = external_long_path_error(
            component="7-Zip",
            path=compatibility_path,
            detail=detail,
        )
        if compatibility_error is not None:
            raise compatibility_error
        raise StandaloneArtifactError(
            f"Native 7-Zip {operation} failed with exit code {return_code}.{suffix}"
        )


def bundled_seven_zip_path(
    application_root: Path,
    *,
    platform_name: str | None = None,
    machine_name: str | None = None,
) -> Path:
    """Resolve the bundled 7-Zip binary for one supported release target."""

    selected_platform = (platform_name or sys.platform).lower()
    selected_machine = (machine_name or platform.machine()).lower()
    architecture = {
        "amd64": "x64",
        "x86_64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(selected_machine)
    target = {
        ("win32", "x64"): ("windows-x64", "7za.exe"),
        ("linux", "x64"): ("linux-x64", "7za"),
        ("darwin", "arm64"): ("macos-arm64", "7za"),
    }.get((selected_platform, architecture or ""))
    if target is None:
        raise StandaloneArtifactError(
            "No bundled native 7-Zip binary supports "
            f"{selected_platform}/{selected_machine}."
        )
    target_directory, filename = target
    return (
        application_root / "third_party" / "bin" / "7zip" / target_directory / filename
    )


def _run_bounded(
    command: tuple[str, ...],
    *,
    cwd: Path,
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    """Run one hidden native command with bounded captured output."""

    startupinfo, creationflags = _hidden_process_options()
    try:
        return subprocess.run(  # noqa: S603
            command,
            cwd=subprocess_working_directory(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            shell=False,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired as error:
        raise StandaloneArtifactError(
            "Native standalone 7-Zip listing timed out."
        ) from error
    except OSError as error:
        raise StandaloneArtifactError(
            "Could not start the bundled native 7-Zip process."
        ) from error


def _hidden_process_options() -> tuple[subprocess.STARTUPINFO | None, int]:
    """Return platform options that suppress a transient console window."""

    if sys.platform != "win32":
        return None, 0
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo, subprocess.CREATE_NO_WINDOW


def _publish_percentages(
    output: str,
    *,
    started_at: float,
    previous_percentage: int,
    callback: SevenZipProgressCallback | None,
) -> tuple[str, int]:
    """Publish increasing percentages and retain a token-boundary suffix."""

    last_percentage = previous_percentage
    for match in _PERCENTAGE_PATTERN.finditer(output):
        percentage = int(match.group(1))
        if percentage > 100 or percentage <= last_percentage:
            continue
        last_percentage = percentage
        _publish_progress(
            percentage=percentage,
            started_at=started_at,
            callback=callback,
        )
    return output[-16:], last_percentage


def _publish_progress(
    *,
    percentage: int,
    started_at: float,
    callback: SevenZipProgressCallback | None,
) -> None:
    """Emit one elapsed and ETA-bearing native progress sample."""

    if callback is None:
        return
    elapsed_seconds = time.monotonic() - started_at
    estimated_remaining_seconds = (
        elapsed_seconds * (100 - percentage) / percentage if percentage > 0 else None
    )
    callback(
        SevenZipExtractionProgress(
            percentage=percentage,
            elapsed_seconds=elapsed_seconds,
            estimated_remaining_seconds=estimated_remaining_seconds,
        )
    )


def _parse_member_paths(output: str) -> tuple[str, ...]:
    """Parse technical-listing member paths after the archive metadata divider."""

    _, separator, member_output = output.partition("----------")
    if not separator:
        return ()
    return tuple(
        line.removeprefix("Path = ")
        for line in member_output.splitlines()
        if line.startswith("Path = ")
    )


def _tail_output(output: str | None, *, limit: int = 2_000) -> str:
    """Return a bounded single-line diagnostic tail from child output."""

    if not output:
        return ""
    normalized = " ".join(output.split())
    return normalized[-limit:]
