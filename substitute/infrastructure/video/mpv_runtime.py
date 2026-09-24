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

"""Load the project-owned libmpv runtime from an absolute verified path."""

from __future__ import annotations

import ctypes.util
from dataclasses import dataclass
import importlib
from pathlib import Path
import platform
import sys
from types import ModuleType
from unittest.mock import patch

from substitute.application.ports.video import VideoRuntimeUnavailableError


class MpvRuntimeError(VideoRuntimeUnavailableError):
    """Report an unavailable or invalid project-owned libmpv runtime."""


@dataclass(frozen=True, slots=True)
class MpvRuntimeTarget:
    """Describe the bundled native library for one release platform."""

    directory_name: str
    library_name: str


class MpvRuntime:
    """Own deterministic loading of python-mpv against one native library."""

    def __init__(self, library_path: Path) -> None:
        """Require one absolute existing native-library path."""

        resolved = library_path.expanduser().resolve()
        if not resolved.is_file():
            raise MpvRuntimeError(
                f"The bundled video runtime is unavailable: {resolved.name}"
            )
        self._library_path = resolved
        self._module: ModuleType | None = None

    @classmethod
    def bundled(cls, *, application_root: Path | None = None) -> MpvRuntime:
        """Resolve the runtime from the application payload for this platform."""

        root = (
            application_root.resolve()
            if application_root is not None
            else Path(__file__).resolve().parents[3]
        )
        target = mpv_runtime_target()
        return cls(
            root
            / "third_party"
            / "bin"
            / "mpv"
            / target.directory_name
            / target.library_name
        )

    @property
    def library_path(self) -> Path:
        """Return the exact native library loaded by this owner."""

        return self._library_path

    def load_module(self) -> ModuleType:
        """Import python-mpv while forcing its lookup to this absolute library."""

        if self._module is not None:
            return self._module
        existing = sys.modules.get("mpv")
        if existing is not None:
            self._verify_loaded_backend(existing)
            self._module = existing
            return existing

        original_find_library = ctypes.util.find_library

        def find_owned_library(name: str) -> str | None:
            """Resolve only python-mpv's libmpv lookup to the owned runtime."""

            if name in {"mpv", "mpv-2.dll", "libmpv-2.dll", "mpv-1.dll"}:
                return str(self._library_path)
            return original_find_library(name)

        with patch.object(
            ctypes.util,
            "find_library",
            side_effect=find_owned_library,
        ):
            try:
                module = importlib.import_module("mpv")
            except (ImportError, OSError) as error:
                raise MpvRuntimeError(
                    f"The bundled video runtime could not be loaded: {self._library_path.name}"
                ) from error
        self._verify_loaded_backend(module)
        self._module = module
        return module

    def _verify_loaded_backend(self, module: ModuleType) -> None:
        """Reject an imported python-mpv module backed by another library."""

        backend = getattr(module, "backend", None)
        loaded_name = getattr(backend, "_name", None)
        if not isinstance(loaded_name, str):
            raise MpvRuntimeError("python-mpv did not expose its loaded runtime path.")
        loaded_path = Path(loaded_name).expanduser().resolve()
        if loaded_path != self._library_path:
            raise MpvRuntimeError(
                "python-mpv was already bound to a non-project video runtime."
            )


def mpv_runtime_target(
    *,
    platform_name: str | None = None,
    machine: str | None = None,
) -> MpvRuntimeTarget:
    """Return the packaged libmpv contract for a supported release host."""

    resolved_platform = platform_name or sys.platform
    resolved_machine = (machine or platform.machine()).strip().lower()
    if resolved_platform == "win32" and resolved_machine in {"amd64", "x86_64"}:
        return MpvRuntimeTarget("windows-x64", "libmpv-2.dll")
    if resolved_platform == "darwin" and resolved_machine in {"arm64", "aarch64"}:
        return MpvRuntimeTarget("macos-arm64", "libmpv.2.dylib")
    if resolved_platform.startswith("linux") and resolved_machine in {
        "amd64",
        "x86_64",
    }:
        return MpvRuntimeTarget("linux-x64", "libmpv.so.2")
    raise MpvRuntimeError(
        "Unsupported video runtime platform: "
        f"{resolved_platform}/{machine or platform.machine()}"
    )


__all__ = ["MpvRuntime", "MpvRuntimeError", "MpvRuntimeTarget", "mpv_runtime_target"]
