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

"""Materialize disposable repair candidates while retaining verified retry inputs."""

from __future__ import annotations

from dataclasses import replace
import logging
import shutil

from launcher.sugarsubstitute_launcher.application.repair.integrity import (
    verify_directory_tree_sha256,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.repair_artifact_storage import (
    create_repair_artifact_directory,
)


_LOGGER = logging.getLogger(__name__)


def stage_repair_attempt(request: PreparedRepairRequest) -> PreparedRepairRequest:
    """Copy and reverify each attempt so rollback cannot consume the retry source."""
    attempt = create_repair_artifact_directory(
        install_root=request.install_root,
        parent=request.install_root
        / ".repair"
        / "staging"
        / request.version
        / "attempts",
        prefix="attempt-",
    )
    for source, name, digest in (
        (request.staged_app_dir, "app", request.staged_app_sha256),
        (request.staged_launcher_dir, "launcher", request.staged_launcher_sha256),
    ):
        verify_directory_tree_sha256(source, expected=digest)
        candidate = attempt / name
        shutil.copytree(source, candidate, symlinks=True)
        verify_directory_tree_sha256(candidate, expected=digest)
    _LOGGER.info("Prepared repair attempt", extra={"attempt_path": str(attempt)})
    return replace(
        request,
        staged_app_dir=attempt / "app",
        staged_launcher_dir=attempt / "launcher",
    )
