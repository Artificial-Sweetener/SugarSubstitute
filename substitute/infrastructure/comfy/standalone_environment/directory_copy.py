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

"""Copy large package trees concurrently with bounded progress reporting."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import time

from substitute.infrastructure.execution.parallel_map import BoundedParallelMapper


DirectoryCopyProgressCallback = Callable[["DirectoryCopyProgress"], None]
_DEFAULT_COPY_PARALLELISM = 50


@dataclass(frozen=True, slots=True)
class DirectoryCopyProgress:
    """Describe current progress through one directory-tree copy."""

    copied_entries: int
    total_entries: int
    elapsed_seconds: float
    estimated_remaining_seconds: float | None


@dataclass(frozen=True, slots=True)
class _DirectoryCopyPlan:
    """Describe the directories, files, and links in one source tree."""

    directories: tuple[Path, ...]
    files: tuple[Path, ...]
    symbolic_links: tuple[Path, ...]

    @property
    def total_entries(self) -> int:
        """Return the progress-bearing file and symbolic-link count."""

        return len(self.files) + len(self.symbolic_links)


class ConcurrentDirectoryCopier:
    """Hydrate a large immutable source tree with bounded concurrent copies."""

    def __init__(self, *, parallelism: int = _DEFAULT_COPY_PARALLELISM) -> None:
        """Store the bounded filesystem-copy parallelism."""

        self._parallel_mapper = BoundedParallelMapper(parallelism=parallelism)

    def copy(
        self,
        source: Path,
        destination: Path,
        *,
        on_progress: DirectoryCopyProgressCallback | None = None,
    ) -> None:
        """Copy one tree while preserving files, modes, and safe link targets."""

        if not source.is_dir():
            raise FileNotFoundError(f"Directory copy source is missing: {source}")
        destination.mkdir(parents=True, exist_ok=True)
        plan = _collect_copy_plan(source)

        started_at = time.monotonic()
        copied_entries = 0
        with self._parallel_mapper as parallel_mapper:
            parallel_mapper.map(
                lambda relative_path: (destination / relative_path).mkdir(
                    parents=True,
                    exist_ok=True,
                ),
                plan.directories,
            )
            for batch_start in range(0, len(plan.files), _DEFAULT_COPY_PARALLELISM):
                batch = plan.files[
                    batch_start : batch_start + _DEFAULT_COPY_PARALLELISM
                ]
                parallel_mapper.map(
                    lambda relative_path: _copy_file(
                        source=source,
                        destination=destination,
                        relative_path=relative_path,
                    ),
                    batch,
                )
                copied_entries += len(batch)
                _emit_progress(
                    on_progress,
                    copied_entries=copied_entries,
                    total_entries=plan.total_entries,
                    started_at=started_at,
                )

        for relative_link in plan.symbolic_links:
            _copy_symbolic_link(
                source=source,
                destination=destination,
                relative_path=relative_link,
            )
            copied_entries += 1
            _emit_progress(
                on_progress,
                copied_entries=copied_entries,
                total_entries=plan.total_entries,
                started_at=started_at,
            )

        if plan.total_entries == 0:
            _emit_progress(
                on_progress,
                copied_entries=0,
                total_entries=0,
                started_at=started_at,
            )


def _collect_copy_plan(source: Path) -> _DirectoryCopyPlan:
    """Collect one tree without traversing directory symbolic links."""

    directories: list[Path] = []
    files: list[Path] = []
    symbolic_links: list[Path] = []
    pending = [source]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                entry_path = Path(entry.path)
                relative_path = entry_path.relative_to(source)
                if entry.is_symlink():
                    symbolic_links.append(relative_path)
                elif entry.is_dir(follow_symlinks=False):
                    directories.append(relative_path)
                    pending.append(entry_path)
                elif entry.is_file(follow_symlinks=False):
                    files.append(relative_path)
    return _DirectoryCopyPlan(
        directories=tuple(sorted(directories)),
        files=tuple(sorted(files)),
        symbolic_links=tuple(sorted(symbolic_links)),
    )


def _copy_file(*, source: Path, destination: Path, relative_path: Path) -> None:
    """Copy one planned file and its metadata into an existing tree."""

    destination_path = destination / relative_path
    shutil.copy2(source / relative_path, destination_path)


def _copy_symbolic_link(
    *,
    source: Path,
    destination: Path,
    relative_path: Path,
) -> None:
    """Recreate one link and rewrite absolute targets that point into the source."""

    source_link = source / relative_path
    destination_link = destination / relative_path
    destination_link.parent.mkdir(parents=True, exist_ok=True)
    target = Path(os.readlink(source_link))
    if target.is_absolute():
        try:
            relative_target = target.relative_to(source)
        except ValueError:
            pass
        else:
            target = destination / relative_target
    os.symlink(
        target,
        destination_link,
        target_is_directory=source_link.resolve().is_dir(),
    )


def _emit_progress(
    callback: DirectoryCopyProgressCallback | None,
    *,
    copied_entries: int,
    total_entries: int,
    started_at: float,
) -> None:
    """Emit one timing-aware progress snapshot when requested."""

    if callback is None:
        return
    elapsed_seconds = time.monotonic() - started_at
    remaining = total_entries - copied_entries
    estimated_remaining_seconds = (
        elapsed_seconds * remaining / copied_entries if copied_entries > 0 else None
    )
    callback(
        DirectoryCopyProgress(
            copied_entries=copied_entries,
            total_entries=total_entries,
            elapsed_seconds=elapsed_seconds,
            estimated_remaining_seconds=estimated_remaining_seconds,
        )
    )
