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

"""Prepare SugarCubes baseline repositories through the libgit2 boundary."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.comfy.nodepack_reconciliation_logger import (
    LogCallback,
    emit_log,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_warning,
)
from substitute.infrastructure.version_control import (
    RepositoryOperationError,
    RepositoryService,
    repository_service,
)

BASE_CUBES_REPOSITORY_URL = "https://github.com/Artificial-Sweetener/Base-Cubes.git"
_LOGGER = get_logger(__name__)


def prepare_sugarcubes_repositories(
    sugarcubes_root: Path,
    *,
    on_log: LogCallback | None = None,
    repositories: RepositoryService | None = None,
) -> None:
    """Initialize local authoring state and synchronize the required base cubes."""

    selected = repositories or repository_service()
    data_root = sugarcubes_root / ".sugarcubes"
    local_root = data_root / "local"
    if not (local_root / ".git").exists():
        try:
            selected.initialize(local_root)
        except RepositoryOperationError as error:
            raise RuntimeError(
                "Could not initialize SugarCubes local authoring storage."
            ) from error

    base_cubes_root = data_root / "Artificial-Sweetener" / "Base-Cubes"
    try:
        if not base_cubes_root.exists():
            selected.clone(
                BASE_CUBES_REPOSITORY_URL,
                base_cubes_root,
                on_progress=on_log,
            )
        elif (base_cubes_root / ".git").exists():
            _synchronize_existing_base_cubes(
                base_cubes_root,
                repositories=selected,
                on_log=on_log,
            )
        else:
            raise RuntimeError(
                "SugarCubes Base-Cubes storage exists without repository metadata."
            )
    except RepositoryOperationError as error:
        raise RuntimeError("Could not synchronize SugarCubes Base-Cubes.") from error


def _synchronize_existing_base_cubes(
    repository_path: Path,
    *,
    repositories: RepositoryService,
    on_log: LogCallback | None,
) -> None:
    """Retain a usable local checkout when it cannot be fast-forwarded safely."""

    try:
        repositories.sync_fast_forward(repository_path, on_progress=on_log)
    except RepositoryOperationError as error:
        log_warning(
            _LOGGER,
            "Retaining existing Base-Cubes checkout after synchronization refusal",
            error_type=type(error).__name__,
            repository=repository_path,
        )
        emit_log(
            on_log,
            "WARNING: SugarCubes[base_cubes_sync_skipped]: "
            "Base-Cubes synchronization skipped: The existing local checkout "
            "was preserved and will be used.",
            operation="sugarcubes_repository_sync",
            outcome="local_checkout_preserved",
        )


__all__ = ["BASE_CUBES_REPOSITORY_URL", "prepare_sugarcubes_repositories"]
