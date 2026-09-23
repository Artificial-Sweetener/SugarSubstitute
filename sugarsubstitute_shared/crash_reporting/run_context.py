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

"""Persist non-secret runtime facts before an application can fail."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Mapping, Self

from sugarsubstitute_shared.crash_reporting.store import _write_json_atomically


RUNTIME_CONTEXT_FILENAME = "runtime-context.json"
STARTUP_OUTPUT_FILENAME = "startup-output.log"
_RUNTIME_CONTEXT_SCHEMA_VERSION = 1
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CrashRunRuntimeContext:
    """Describe stable runtime facts available independently of an exception."""

    process_id: int
    application_version: str | None
    platform: str
    python_version: str
    launch_arguments: tuple[str, ...]
    install_root: str

    def __post_init__(self) -> None:
        """Reject a runtime context that cannot identify its process."""

        if self.process_id <= 0:
            raise ValueError("Crash runtime context requires a positive process ID.")

    def to_json(self) -> dict[str, object]:
        """Return the versioned durable representation."""

        return {
            "schema_version": _RUNTIME_CONTEXT_SCHEMA_VERSION,
            "process_id": self.process_id,
            "application_version": self.application_version,
            "platform": self.platform,
            "python_version": self.python_version,
            "launch_arguments": list(self.launch_arguments),
            "install_root": self.install_root,
        }

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse and validate one durable runtime context."""

        if not isinstance(payload, Mapping):
            raise ValueError("Crash runtime context must be a JSON object.")
        if payload.get("schema_version") != _RUNTIME_CONTEXT_SCHEMA_VERSION:
            raise ValueError("Crash runtime context schema is unsupported.")
        process_id = payload.get("process_id")
        application_version = payload.get("application_version")
        platform_name = payload.get("platform")
        python_version = payload.get("python_version")
        launch_arguments = payload.get("launch_arguments")
        install_root = payload.get("install_root")
        if not isinstance(process_id, int) or isinstance(process_id, bool):
            raise ValueError("Crash runtime process ID is invalid.")
        if application_version is not None and not isinstance(application_version, str):
            raise ValueError("Crash runtime application version is invalid.")
        if not isinstance(platform_name, str) or not platform_name:
            raise ValueError("Crash runtime platform is invalid.")
        if not isinstance(python_version, str) or not python_version:
            raise ValueError("Crash runtime Python version is invalid.")
        if not isinstance(launch_arguments, list) or any(
            not isinstance(argument, str) for argument in launch_arguments
        ):
            raise ValueError("Crash runtime launch arguments are invalid.")
        if not isinstance(install_root, str) or not install_root:
            raise ValueError("Crash runtime install root is invalid.")
        return cls(
            process_id=process_id,
            application_version=application_version,
            platform=platform_name,
            python_version=python_version,
            launch_arguments=tuple(launch_arguments),
            install_root=install_root,
        )


class CrashRunRuntimeContextStore:
    """Own runtime facts below the temporary diagnostic-run namespace."""

    def __init__(self, run_root: Path) -> None:
        """Bind runtime context storage to the temporary run namespace."""

        self._run_root = run_root

    def save(self, run_id: str, context: CrashRunRuntimeContext) -> Path:
        """Atomically persist runtime facts and return their path."""

        path = self.path(run_id)
        _write_json_atomically(path, context.to_json())
        return path

    def load(self, run_id: str) -> CrashRunRuntimeContext | None:
        """Return valid runtime facts or preserve and report unreadable evidence."""

        path = self.path(run_id)
        try:
            return CrashRunRuntimeContext.from_json(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except FileNotFoundError:
            return None
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            _LOGGER.warning(
                "Crash runtime context could not be read.",
                extra={"run_id": run_id, "path": str(path)},
                exc_info=True,
            )
            return None

    def path(self, run_id: str) -> Path:
        """Return the contained runtime context path for one safe run ID."""

        if not run_id or run_id in {".", ".."} or "/" in run_id or "\\" in run_id:
            raise ValueError("Crash run identifier is unsafe.")
        return self._run_root / run_id / RUNTIME_CONTEXT_FILENAME

    def run_ids_for_process(self, process_id: int) -> tuple[str, ...]:
        """Return valid run identities whose durable context names one process."""

        if process_id <= 0:
            raise ValueError("Crash runtime process ID must be positive.")
        if not self._run_root.is_dir():
            return ()
        matches: list[str] = []
        for directory in sorted(self._run_root.iterdir(), key=lambda path: path.name):
            if not directory.is_dir() or directory.is_symlink():
                continue
            context = self.load(directory.name)
            if context is not None and context.process_id == process_id:
                matches.append(directory.name)
        return tuple(matches)


__all__ = [
    "CrashRunRuntimeContext",
    "CrashRunRuntimeContextStore",
    "RUNTIME_CONTEXT_FILENAME",
    "STARTUP_OUTPUT_FILENAME",
]
