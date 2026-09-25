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

"""Verify deterministic project-owned libmpv runtime selection."""

from __future__ import annotations

import ctypes.util
import importlib
import os
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import patch

import pytest

from substitute.infrastructure.video.mpv_runtime import (
    MpvRuntime,
    MpvRuntimeError,
    mpv_runtime_target,
)


def test_runtime_requires_existing_absolute_library(tmp_path: Path) -> None:
    """Reject a missing native runtime before importing python-mpv."""

    with pytest.raises(MpvRuntimeError, match="unavailable"):
        MpvRuntime(tmp_path / "libmpv-2.dll")


def test_runtime_forces_python_binding_to_owned_library(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve python-mpv's library lookup to the exact packaged path."""

    library = tmp_path / "libmpv-2.dll"
    library.write_bytes(b"native-placeholder")
    module = ModuleType("mpv")
    observed: list[str | None] = []

    class Backend:
        """Expose the ctypes backend path used by python-mpv."""

        _name = str(library.resolve())

    module.backend = Backend()  # type: ignore[attr-defined]

    def import_binding(name: str) -> ModuleType:
        """Model python-mpv querying ctypes during module import."""

        assert name == "mpv"
        observed.append(ctypes.util.find_library("mpv"))
        return module

    monkeypatch.delitem(sys.modules, "mpv", raising=False)
    with patch.object(importlib, "import_module", side_effect=import_binding):
        loaded = MpvRuntime(library).load_module()

    assert loaded is module
    assert observed == [str(library.resolve())]


def test_windows_runtime_activates_and_retains_sibling_dll_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve dynamically linked runtime dependencies beside libmpv."""

    library = tmp_path / "runtime" / "libmpv-2.dll"
    library.parent.mkdir()
    library.write_bytes(b"native-placeholder")
    module = ModuleType("mpv")

    class Backend:
        """Expose the expected project-owned backend path."""

        _name = str(library.resolve())

    class DirectoryHandle:
        """Record whether the dependency search handle remains active."""

        closed = False

        def close(self) -> None:
            """Record explicit release of the fake search directory."""

            self.closed = True

    module.backend = Backend()  # type: ignore[attr-defined]
    handle = DirectoryHandle()
    observed: list[str] = []

    def add_dll_directory(path: str) -> DirectoryHandle:
        """Capture the exact directory activated by the runtime owner."""

        observed.append(path)
        return handle

    monkeypatch.delitem(sys.modules, "mpv", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "add_dll_directory", add_dll_directory, raising=False)
    runtime = MpvRuntime(library)
    with patch.object(importlib, "import_module", return_value=module):
        assert runtime.load_module() is module

    assert observed == [str(library.parent.resolve())]
    assert handle.closed is False


def test_runtime_rejects_binding_loaded_from_another_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never silently accept a PATH-selected or system libmpv."""

    owned = tmp_path / "owned" / "libmpv-2.dll"
    owned.parent.mkdir()
    owned.write_bytes(b"owned")
    foreign = tmp_path / "foreign" / "libmpv-2.dll"
    foreign.parent.mkdir()
    foreign.write_bytes(b"foreign")
    module = ModuleType("mpv")

    class Backend:
        """Expose an already-imported foreign backend path."""

        _name = str(foreign.resolve())

    module.backend = Backend()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mpv", module)

    with pytest.raises(MpvRuntimeError, match="non-project"):
        MpvRuntime(owned).load_module()


@pytest.mark.parametrize(
    ("platform_name", "machine", "directory", "library"),
    [
        ("win32", "AMD64", "windows-x64", "libmpv-2.dll"),
        ("linux", "x86_64", "linux-x64", "libmpv.so.2"),
        ("darwin", "arm64", "macos-arm64", "libmpv.2.dylib"),
    ],
)
def test_runtime_target_maps_supported_release_hosts(
    platform_name: str,
    machine: str,
    directory: str,
    library: str,
) -> None:
    """Keep runtime payload paths explicit for every release target."""

    target = mpv_runtime_target(platform_name=platform_name, machine=machine)

    assert target.directory_name == directory
    assert target.library_name == library


def test_runtime_target_rejects_unsupported_host() -> None:
    """Fail closed instead of searching the unsupported host system."""

    with pytest.raises(MpvRuntimeError, match="Unsupported"):
        mpv_runtime_target(platform_name="linux", machine="arm64")
