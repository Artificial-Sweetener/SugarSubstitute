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

"""Allocate short, app-owned scratch workspaces for external components."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from uuid import uuid4

from sugarsubstitute_shared.external_path_contract import ExternalPathContract
from sugarsubstitute_shared.windows_long_paths import operational_path

_SCRATCH_PARENT_NAME = ".sugarsubstitute-temp"
_OWNERSHIP_SENTINEL_NAME = ".sugarsubstitute-scratch"


class ExternalScratchAllocationError(RuntimeError):
    """Report that no safe scratch location satisfies an external contract."""


@dataclass(frozen=True, slots=True)
class ExternalScratchWorkspace:
    """Own one reserved external-process scratch directory."""

    root: Path
    _cleanup_parent_when_empty: Path | None = None

    @classmethod
    def reserve(
        cls,
        root: Path,
        *,
        cleanup_parent_when_empty: Path | None = None,
    ) -> ExternalScratchWorkspace:
        """Reserve an exact root and record ownership for safe cleanup."""

        operational_root = operational_path(root)
        operational_root.mkdir(parents=False, exist_ok=False)
        try:
            (operational_root / _OWNERSHIP_SENTINEL_NAME).write_text(
                "SugarSubstitute external scratch\n",
                encoding="utf-8",
            )
        except Exception:
            operational_root.rmdir()
            raise
        return cls(
            root=Path(str(operational_root)),
            _cleanup_parent_when_empty=cleanup_parent_when_empty,
        )

    def cleanup(self) -> None:
        """Delete only the scratch directory carrying our ownership sentinel."""

        resolved_root = operational_path(self.root).resolve()
        if resolved_root == Path(resolved_root.anchor):
            raise RuntimeError(f"Refusing to clean filesystem root: {resolved_root}")
        sentinel = resolved_root / _OWNERSHIP_SENTINEL_NAME
        if not sentinel.is_file():
            raise RuntimeError(
                f"Refusing to clean unowned external scratch root: {resolved_root}"
            )
        shutil.rmtree(resolved_root, onexc=_clear_readonly_and_retry)
        cleanup_parent = self._cleanup_parent_when_empty
        if cleanup_parent is None:
            return
        try:
            operational_path(cleanup_parent).rmdir()
        except OSError:
            pass


def allocate_external_scratch(
    *,
    preferred_storage_path: Path,
    namespace: str,
    contract: ExternalPathContract,
) -> ExternalScratchWorkspace:
    """Reserve the first writable scratch root satisfying the path contract."""

    token = _scratch_token(namespace)
    failures: list[str] = []
    for parent in _candidate_parents(preferred_storage_path):
        root = parent / token
        if not contract.accepts(root):
            failures.append(
                f"{parent} exceeds the {contract.maximum_windows_root_length}-character root budget"
            )
            continue
        parent_created = False
        try:
            parent.mkdir(parents=True, exist_ok=False)
            parent_created = True
        except FileExistsError:
            pass
        except OSError as error:
            failures.append(f"{parent}: {error}")
            continue
        try:
            return ExternalScratchWorkspace.reserve(
                root,
                cleanup_parent_when_empty=(
                    parent
                    if parent_created or parent.name == _SCRATCH_PARENT_NAME
                    else None
                ),
            )
        except OSError as error:
            failures.append(f"{root}: {error}")
            if parent_created:
                try:
                    parent.rmdir()
                except OSError:
                    pass
    detail = "; ".join(failures) or "no candidate scratch roots were available"
    raise ExternalScratchAllocationError(
        f"Could not allocate {contract.component} scratch storage. {detail}"
    )


def _candidate_parents(preferred_storage_path: Path) -> tuple[Path, ...]:
    """Return ordered same-volume and user-temporary scratch parents."""

    preferred = Path(preferred_storage_path).expanduser().absolute()
    system_temp_parent = Path(tempfile.gettempdir())
    if sys.platform == "win32" and preferred.anchor:
        volume_parent = Path(preferred.anchor) / _SCRATCH_PARENT_NAME
        if volume_parent != system_temp_parent:
            return volume_parent, system_temp_parent
    return (preferred.parent / _SCRATCH_PARENT_NAME, system_temp_parent)


def _scratch_token(namespace: str) -> str:
    """Return a compact collision-resistant directory name."""

    normalized = "".join(
        character.lower()
        for character in namespace
        if character.isascii() and (character.isalnum() or character == "-")
    ).strip("-")
    if not normalized:
        raise ValueError("External scratch namespace must contain a safe character.")
    return f"{normalized[:16]}-{uuid4().hex[:12]}"


def _clear_readonly_and_retry(
    function: object,
    path: str,
    _error: BaseException,
) -> None:
    """Clear a read-only scratch entry before retrying its removal once."""

    os.chmod(path, stat.S_IWRITE)
    if not callable(function):
        raise TypeError("Scratch cleanup callback is not callable.")
    function(path)


__all__ = [
    "ExternalScratchAllocationError",
    "ExternalScratchWorkspace",
    "allocate_external_scratch",
]
