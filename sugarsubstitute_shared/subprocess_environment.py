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

"""Build subprocess environments independent from frozen parent runtimes."""

from __future__ import annotations

import contextlib
import ctypes
import os
from pathlib import Path
import sys
from collections.abc import Iterator, Mapping


def clean_frozen_parent_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Remove PyInstaller runtime state before starting an external child."""

    child_environment = dict(os.environ if environment is None else environment)
    frozen_root_value = getattr(sys, "_MEIPASS", None)
    if not isinstance(frozen_root_value, str) or not frozen_root_value:
        return child_environment

    frozen_root = Path(frozen_root_value)
    _restore_original_library_path(child_environment, "LD_LIBRARY_PATH")
    _restore_original_library_path(child_environment, "DYLD_LIBRARY_PATH")
    for variable_name in (
        "PATH",
        "LD_LIBRARY_PATH",
        "DYLD_LIBRARY_PATH",
        "DYLD_FALLBACK_LIBRARY_PATH",
        "DYLD_FRAMEWORK_PATH",
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        "QML2_IMPORT_PATH",
        "QML_IMPORT_PATH",
        "PYTHONHOME",
    ):
        _remove_frozen_path_entries(
            child_environment,
            variable_name,
            frozen_root=frozen_root,
        )
    for variable_name in tuple(child_environment):
        if variable_name.startswith("_PYI_"):
            child_environment.pop(variable_name, None)
    return child_environment


@contextlib.contextmanager
def standard_child_process_dll_search_path() -> Iterator[None]:
    """Prevent a frozen Windows parent's private DLL path reaching a child."""

    if sys.platform != "win32" or not bool(getattr(sys, "frozen", False)):
        yield
        return

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    meipass = getattr(sys, "_MEIPASS", None)
    kernel32.SetDllDirectoryW(None)
    try:
        yield
    finally:
        if isinstance(meipass, str) and meipass:
            kernel32.SetDllDirectoryW(meipass)


def _restore_original_library_path(
    environment: dict[str, str],
    variable_name: str,
) -> None:
    """Restore a loader path saved by the PyInstaller bootloader."""

    original_name = f"{variable_name}_ORIG"
    if original_name not in environment:
        return
    original_value = environment.pop(original_name)
    if original_value:
        environment[variable_name] = original_value
    else:
        environment.pop(variable_name, None)


def _remove_frozen_path_entries(
    environment: dict[str, str],
    variable_name: str,
    *,
    frozen_root: Path,
) -> None:
    """Remove path-list entries owned by the frozen extraction root."""

    value = environment.get(variable_name)
    if not value:
        return
    retained = tuple(
        entry
        for entry in value.split(os.pathsep)
        if entry and not _is_relative_to(Path(entry), frozen_root)
    )
    if retained:
        environment[variable_name] = os.pathsep.join(retained)
    else:
        environment.pop(variable_name, None)


def _is_relative_to(path: Path, parent: Path) -> bool:
    """Return whether one path resolves beneath another path."""

    try:
        path.resolve().relative_to(parent.resolve())
    except (OSError, ValueError):
        return False
    return True


__all__ = [
    "clean_frozen_parent_environment",
    "standard_child_process_dll_search_path",
]
