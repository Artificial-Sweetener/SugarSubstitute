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

"""Run bounded self-contained repository clones outside the GUI interpreter."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from substitute.infrastructure.filesystem import remove_app_owned_path
from substitute.infrastructure.version_control.repository import (
    RepositoryOperationError,
)
from sugarsubstitute_shared.windows_long_paths import (
    exceeds_windows_legacy_path_limit,
    external_long_path_error,
    operational_path,
    subprocess_path,
    subprocess_working_directory,
)


_DEFAULT_CLONE_TIMEOUT_SECONDS = 120.0
_OUTPUT_TAIL_LIMIT = 2_000
_LOGGER = logging.getLogger(__name__)


class Pygit2CloneProcess:
    """Clone one repository shallowly through bundled pygit2 in a child process."""

    def __init__(
        self,
        *,
        python_executable: Path | None = None,
        application_root: Path | None = None,
        timeout_seconds: float = _DEFAULT_CLONE_TIMEOUT_SECONDS,
    ) -> None:
        """Store the interpreter, import root, and bounded network timeout."""

        if timeout_seconds <= 0:
            raise ValueError("Repository clone timeout must be positive.")
        self._python_executable = python_executable or Path(sys.executable)
        self._application_root = application_root or Path(__file__).resolve().parents[3]
        self._timeout_seconds = timeout_seconds

    def clone(self, repository_url: str, target_path: Path) -> None:
        """Run a depth-one clone and remove partial output on every failure."""

        target_path = operational_path(target_path)
        staging_root: Path | None = None
        clone_target = target_path
        if exceeds_windows_legacy_path_limit(target_path):
            staging_root = Path(tempfile.mkdtemp(prefix="sugarsubstitute-git-"))
            clone_target = staging_root / "repository"
        command = (
            subprocess_path(self._python_executable),
            "-m",
            "substitute.infrastructure.version_control.clone_entry",
            repository_url,
            subprocess_path(clone_target),
        )
        environment = dict(os.environ)
        existing_python_path = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = os.pathsep.join(
            part
            for part in (subprocess_path(self._application_root), existing_python_path)
            if part
        )
        startupinfo, creationflags = _hidden_process_options()
        try:
            completed = subprocess.run(  # noqa: S603
                command,
                cwd=subprocess_working_directory(self._application_root),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout_seconds,
                check=False,
                shell=False,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired as error:
            _discard_clone_work(clone_target, staging_root=staging_root)
            raise RepositoryOperationError(
                f"Repository clone timed out after {self._timeout_seconds:g} seconds: "
                f"{repository_url}"
            ) from error
        except OSError as error:
            _discard_clone_work(clone_target, staging_root=staging_root)
            compatibility_error = external_long_path_error(
                component="pygit2",
                path=clone_target,
                detail=error,
            )
            if compatibility_error is not None:
                raise compatibility_error from error
            raise RepositoryOperationError(
                f"Could not start the bundled repository clone process: {error}"
            ) from error

        if completed.returncode == 0:
            if staging_root is not None:
                try:
                    shutil.copytree(clone_target, target_path)
                except (OSError, shutil.Error):
                    _LOGGER.exception(
                        "Failed to promote staged repository clone | target=%s",
                        target_path,
                    )
                    _discard_partial_clone(target_path)
                    raise
                finally:
                    _discard_staging_root(staging_root)
            return
        _discard_clone_work(clone_target, staging_root=staging_root)
        detail = _tail_output(completed.stdout)
        compatibility_error = external_long_path_error(
            component="pygit2",
            path=clone_target,
            detail=detail,
        )
        if compatibility_error is not None:
            raise compatibility_error
        suffix = f" Details: {detail}" if detail else ""
        raise RepositoryOperationError(
            f"Repository clone process failed with exit code "
            f"{completed.returncode}.{suffix}"
        )


def _hidden_process_options() -> tuple[subprocess.STARTUPINFO | None, int]:
    """Return platform options that suppress a transient console window."""

    if sys.platform != "win32":
        return None, 0
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo, subprocess.CREATE_NO_WINDOW


def _discard_clone_work(
    clone_target: Path,
    *,
    staging_root: Path | None,
) -> None:
    """Remove partial clone output and its optional short-path staging root."""

    _discard_partial_clone(clone_target)
    if staging_root is not None:
        _discard_staging_root(staging_root)


def _discard_staging_root(staging_root: Path) -> None:
    """Best-effort remove one app-owned clone staging directory with diagnostics."""

    try:
        remove_app_owned_path(staging_root)
    except OSError:
        _LOGGER.warning(
            "Could not remove repository clone staging root | root=%s",
            staging_root,
            exc_info=True,
        )


def _discard_partial_clone(target_path: Path) -> None:
    """Best-effort remove app-owned clone output without masking clone failure."""

    try:
        remove_app_owned_path(target_path)
    except OSError:
        _LOGGER.warning(
            "Could not remove partial repository clone | target=%s",
            target_path,
            exc_info=True,
        )


def _tail_output(output: str | None) -> str:
    """Return a bounded single-line diagnostic tail from clone output."""

    if not output:
        return ""
    return " ".join(output.split())[-_OUTPUT_TAIL_LIMIT:]
