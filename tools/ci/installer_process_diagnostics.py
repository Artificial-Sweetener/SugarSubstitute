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

"""Render portable process identity for installer qualification failures."""

from __future__ import annotations

import json

import psutil  # type: ignore[import-untyped]


def process_tree_diagnostics(pid: int) -> str:
    """Render bounded non-secret identity for one qualification process tree."""

    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return f"<launcher process {pid} already exited>"
    except psutil.AccessDenied:
        return f"<launcher process {pid} could not be inspected>"
    try:
        processes = (root, *root.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        processes = (root,)
    records: list[dict[str, object]] = []
    for process in processes:
        try:
            opened_files = [
                str(open_file.path) for open_file in process.open_files()[:20]
            ]
            records.append(
                {
                    "cmdline": [str(argument) for argument in process.cmdline()],
                    "cpu_times": [float(value) for value in process.cpu_times()[:4]],
                    "cwd": str(process.cwd()),
                    "exe": str(process.exe()),
                    "mapped_runtime_paths": _mapped_runtime_paths(process),
                    "name": str(process.name()),
                    "num_threads": int(process.num_threads()),
                    "open_files": opened_files,
                    "pid": int(process.pid),
                    "ppid": int(process.ppid()),
                    "status": str(process.status()),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            records.append({"pid": int(process.pid), "status": "unavailable"})
    return json.dumps(records, indent=2, sort_keys=True)


def _mapped_runtime_paths(process: psutil.Process) -> list[str]:
    """Return relevant mappings when the host psutil build exposes them."""

    if not hasattr(process, "memory_maps"):
        return []
    try:
        return sorted(
            {
                str(memory_map.path)
                for memory_map in process.memory_maps(grouped=True)
                if _is_relevant_runtime_mapping(str(memory_map.path))
            }
        )[:60]
    except (psutil.NoSuchProcess, psutil.AccessDenied, NotImplementedError):
        return []


def _is_relevant_runtime_mapping(path: str) -> bool:
    """Return whether one mapped file identifies the frozen startup subsystem."""

    normalized = path.casefold()
    return any(
        marker in normalized
        for marker in (
            "python",
            "pyside",
            "qt6",
            "libqt",
            "ssl",
            "truststore",
        )
    )


__all__ = ["process_tree_diagnostics"]
