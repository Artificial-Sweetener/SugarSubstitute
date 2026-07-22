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

"""Define representative upstream releases for Comfy compatibility proof."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComfySupportMatrixEntry:
    """Describe one real ComfyUI and integrated Manager release pair."""

    comfyui_tag: str
    manager_version: str
    supports_pygit2: bool


@dataclass(frozen=True, slots=True)
class ComfyUpdateMatrixEntry:
    """Describe one in-place forward update between reviewed upstream releases."""

    source_tag: str
    target_tag: str


COMFY_RELEASE_CONTRACTS: tuple[ComfySupportMatrixEntry, ...] = (
    ComfySupportMatrixEntry("v0.15.0", "4.1b1", False),
    ComfySupportMatrixEntry("v0.17.0", "4.1b2", False),
    ComfySupportMatrixEntry("v0.18.0", "4.1b6", False),
    ComfySupportMatrixEntry("v0.19.0", "4.1", False),
    ComfySupportMatrixEntry("v0.20.0", "4.2.1", True),
    ComfySupportMatrixEntry("v0.24.0", "4.2.1", True),
    ComfySupportMatrixEntry("v0.25.0", "4.2.2", True),
    ComfySupportMatrixEntry("v0.28.2", "4.2.2", True),
)

COMFY_SUPPORT_MATRIX: tuple[ComfySupportMatrixEntry, ...] = tuple(
    entry
    for entry in COMFY_RELEASE_CONTRACTS
    if entry.comfyui_tag
    in {"v0.15.0", "v0.17.0", "v0.18.0", "v0.19.0", "v0.20.0", "v0.28.2"}
)

COMFY_UPDATE_MATRIX: tuple[ComfyUpdateMatrixEntry, ...] = (
    ComfyUpdateMatrixEntry("v0.15.0", "v0.19.0"),
    ComfyUpdateMatrixEntry("v0.19.0", "v0.20.0"),
    ComfyUpdateMatrixEntry("v0.20.0", "v0.24.0"),
    ComfyUpdateMatrixEntry("v0.24.0", "v0.25.0"),
    ComfyUpdateMatrixEntry("v0.25.0", "v0.28.2"),
    ComfyUpdateMatrixEntry("v0.15.0", "v0.24.0"),
)


def matrix_entry(comfyui_tag: str) -> ComfySupportMatrixEntry:
    """Return the declared matrix entry for one exact upstream tag."""

    for entry in COMFY_RELEASE_CONTRACTS:
        if entry.comfyui_tag == comfyui_tag:
            return entry
    supported = ", ".join(entry.comfyui_tag for entry in COMFY_RELEASE_CONTRACTS)
    raise ValueError(
        f"Unknown ComfyUI matrix tag {comfyui_tag!r}; expected {supported}."
    )


__all__ = [
    "COMFY_RELEASE_CONTRACTS",
    "COMFY_SUPPORT_MATRIX",
    "COMFY_UPDATE_MATRIX",
    "ComfySupportMatrixEntry",
    "ComfyUpdateMatrixEntry",
    "matrix_entry",
]
