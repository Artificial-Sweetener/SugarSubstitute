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

"""Collect bounded product and system identity for supervisor crash reports."""

from __future__ import annotations

import ast
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
from collections.abc import Callable

import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher import __version__ as LAUNCHER_VERSION
from launcher.sugarsubstitute_launcher.application.repair.payload_version import (
    RepairPayloadVersionError,
    inspect_app_payload_version,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from sugarsubstitute_shared.application_readiness import READINESS_SCHEMA_VERSION
from sugarsubstitute_shared.crash_reporting.diagnostic_context import (
    CrashDiagnosticContext,
    DiagnosticValue,
)
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord


def collect_crash_diagnostic_context(layout: InstallLayout) -> CrashDiagnosticContext:
    """Capture complete bounded diagnostics without depending on application startup."""

    comfy_root = layout.root / "comfyui"
    return CrashDiagnosticContext(
        substitute_version=_collect(
            "application_payload",
            lambda: inspect_app_payload_version(layout.app_dir),
            expected=(RepairPayloadVersionError,),
        ),
        substitute_release_version=_collect(
            "launcher_state",
            lambda: _installed_application_version(layout),
        ),
        supervising_launcher_version=DiagnosticValue.available(
            LAUNCHER_VERSION, source="running_launcher"
        ),
        installed_launcher_version=_collect(
            "launcher_installation_record",
            lambda: _installed_launcher_version(layout),
        ),
        comfyui_version=_collect(
            "comfyui_version.py",
            lambda: _literal_assignment(
                comfy_root / "comfyui_version.py", "__version__"
            ),
        ),
        comfyui_commit=_collect(
            "comfyui_git_head",
            lambda: _git_head(comfy_root),
        ),
        operating_system=_collect("python_platform", platform.platform),
        system_architecture=_collect(
            "python_platform", lambda: platform.machine() or platform.architecture()[0]
        ),
        python_version=DiagnosticValue.available(sys.version, source="python_runtime"),
        python_architecture=DiagnosticValue.available(
            f"{struct.calcsize('P') * 8}-bit", source="python_runtime"
        ),
        processor=_collect(
            "python_platform",
            lambda: platform.processor() or platform.uname().processor,
        ),
        logical_processor_count=_collect(
            "operating_system",
            lambda: _required_value(os.cpu_count(), "logical processor count"),
        ),
        physical_memory=_collect(
            "psutil",
            lambda: _format_memory(int(psutil.virtual_memory().total)),
        ),
        gpu=_collect("nvidia-smi", _nvidia_gpu_names),
        readiness_schema=DiagnosticValue.available(
            READINESS_SCHEMA_VERSION, source="running_launcher"
        ),
    )


def _collect(
    source: str,
    reader: Callable[[], object],
    *,
    expected: tuple[type[Exception], ...] = (),
) -> DiagnosticValue:
    """Convert a bounded diagnostic reader into an explicit value outcome."""

    handled_errors = expected + (
        OSError,
        UnicodeError,
        SyntaxError,
        ValueError,
        psutil.Error,
        subprocess.SubprocessError,
    )
    try:
        return DiagnosticValue.available(reader(), source=source)
    except handled_errors as error:
        return DiagnosticValue.unavailable(
            _error_reason(error),
            source=source,
        )


def _installed_application_version(layout: InstallLayout) -> str:
    """Return the application version recorded by update ownership."""

    version = LauncherUpdateState.load(layout.state_path).installed_app_version
    return _required_value(version, "installed application version")


def _installed_launcher_version(layout: InstallLayout) -> str:
    """Return the launcher version recorded after successful promotion."""

    record = LauncherInstallationRecord.load(layout.launcher_installation_path)
    return _required_value(
        record.version if record is not None else None,
        "installed launcher version",
    )


def _literal_assignment(path: Path, name: str) -> str:
    """Read one literal module assignment without executing external code."""

    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: list[str] = []
    for statement in module.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        if not any(
            isinstance(target, ast.Name) and target.id == name for target in targets
        ):
            continue
        if isinstance(statement.value, ast.Constant) and isinstance(
            statement.value.value, str
        ):
            values.append(statement.value.value)
    if len(values) != 1 or not values[0]:
        raise ValueError(f"Expected one literal {name} assignment.")
    return values[0]


def _git_head(root: Path) -> str:
    """Resolve checkout HEAD without invoking Git or trusting hooks."""

    git_dir = _git_directory(root)
    head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        reference = head.removeprefix("ref: ")
        loose_reference = git_dir / reference
        head = (
            loose_reference.read_text(encoding="utf-8").strip()
            if loose_reference.is_file()
            else _packed_reference(git_dir, reference)
        )
    if len(head) < 7 or any(
        character not in "0123456789abcdefABCDEF" for character in head
    ):
        raise ValueError("ComfyUI Git HEAD is invalid")
    return head


def _git_directory(root: Path) -> Path:
    """Return the real Git metadata directory for normal and linked checkouts."""

    marker = root / ".git"
    if marker.is_dir():
        return marker
    if not marker.is_file():
        raise ValueError("ComfyUI checkout has no readable Git metadata")
    content = marker.read_text(encoding="utf-8").strip()
    if not content.startswith("gitdir: "):
        raise ValueError("ComfyUI Git metadata pointer is invalid")
    git_dir = Path(content.removeprefix("gitdir: "))
    if not git_dir.is_absolute():
        git_dir = marker.parent / git_dir
    if not git_dir.is_dir():
        raise ValueError("ComfyUI Git metadata directory is unavailable")
    return git_dir.resolve()


def _packed_reference(git_dir: Path, reference: str) -> str:
    """Resolve a packed Git reference without executing repository code."""

    packed_refs = (git_dir / "packed-refs").read_text(encoding="utf-8")
    suffix = f" {reference}"
    matches = [
        line.split(" ", 1)[0]
        for line in packed_refs.splitlines()
        if not line.startswith(("#", "^")) and line.endswith(suffix)
    ]
    if len(matches) != 1:
        raise ValueError("ComfyUI Git HEAD reference is unavailable")
    return matches[0]


def _nvidia_gpu_names() -> str:
    """Return NVIDIA adapter names through a strictly bounded vendor query."""

    executable = shutil.which("nvidia-smi")
    if executable is None:
        raise ValueError("no bounded GPU information provider is available")
    try:
        result = subprocess.run(
            [executable, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2.0,
            check=False,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("GPU query exceeded 2 seconds") from error
    names = tuple(line.strip() for line in result.stdout.splitlines() if line.strip())
    if result.returncode != 0 or not names:
        raise ValueError(f"GPU query exited with code {result.returncode}")
    return ", ".join(names)


def _format_memory(total_bytes: int) -> str:
    """Render physical memory with exact bytes and a readable binary size."""

    if total_bytes <= 0:
        raise ValueError("physical memory was not positive")
    return f"{total_bytes} bytes ({total_bytes / (1024**3):.1f} GiB)"


def _required_value(value: object | None, label: str) -> str:
    """Return one nonempty value or identify its absence."""

    if value is None or not str(value).strip():
        raise ValueError(f"{label} is unavailable")
    return str(value)


def _error_reason(error: Exception) -> str:
    """Return a path-free stable reason suitable for a copied report."""

    if isinstance(error, FileNotFoundError):
        return "source file does not exist"
    if isinstance(error, RepairPayloadVersionError):
        return "application payload version metadata is invalid or unreadable"
    if isinstance(error, SyntaxError):
        return "source file syntax is invalid"
    if isinstance(error, UnicodeError):
        return "source text encoding is invalid"
    if isinstance(error, psutil.Error):
        return "system information query failed"
    if isinstance(error, subprocess.SubprocessError):
        return "external system information query failed"
    if isinstance(error, OSError):
        return "operating system could not read the source"
    return str(error) or "source value is invalid or unavailable"


__all__ = ["collect_crash_diagnostic_context"]
