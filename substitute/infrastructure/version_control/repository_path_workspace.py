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

"""Expose repositories to Windows components through short path aliases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from types import TracebackType

from sugarsubstitute_shared.external_path_contract import ExternalPathContract
from sugarsubstitute_shared.external_scratch import (
    ExternalScratchWorkspace,
    allocate_external_scratch,
)
from sugarsubstitute_shared.windows_directory_junction import (
    create_windows_directory_junction,
)
from sugarsubstitute_shared.windows_long_paths import operational_path

REPOSITORY_DESCENDANT_BUDGET = 190
_ALIAS_DIRECTORY_LENGTH = len("\\repository")
REPOSITORY_PATH_CONTRACT = ExternalPathContract(
    component="pygit2 repository access",
    reserved_descendant_length=(_ALIAS_DIRECTORY_LENGTH + REPOSITORY_DESCENDANT_BUDGET),
)


@dataclass(frozen=True, slots=True)
class RepositoryPathWorkspace:
    """Own one short-lived path through which libgit2 accesses a repository."""

    target_path: Path
    access_path: Path
    _scratch: ExternalScratchWorkspace | None = None

    @classmethod
    def reserve(
        cls,
        target_path: Path,
        *,
        create_target: bool = False,
    ) -> RepositoryPathWorkspace:
        """Expose an existing target, creating it only for creation workflows."""

        operational_target = operational_path(target_path)
        if create_target:
            operational_target.mkdir(parents=True, exist_ok=True)
        elif not operational_target.is_dir():
            raise FileNotFoundError(
                f"Repository path is not a directory: {operational_target}"
            )
        if sys.platform != "win32":
            return cls(
                target_path=operational_target,
                access_path=operational_target,
            )
        scratch = allocate_external_scratch(
            preferred_storage_path=operational_target,
            namespace="git-access",
            contract=REPOSITORY_PATH_CONTRACT,
        )
        access_path = scratch.root / "repository"
        try:
            create_windows_directory_junction(
                junction=access_path,
                target=operational_target,
            )
        except Exception:
            scratch.cleanup()
            raise
        return cls(
            target_path=operational_target,
            access_path=access_path,
            _scratch=scratch,
        )

    def cleanup(self) -> None:
        """Remove the short alias without changing repository contents."""

        if self._scratch is not None:
            self._scratch.cleanup()

    def __enter__(self) -> Path:
        """Return the repository path safe for the external component."""

        return self.access_path

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Release the transient alias after repository access."""

        self.cleanup()


__all__ = [
    "REPOSITORY_DESCENDANT_BUDGET",
    "REPOSITORY_PATH_CONTRACT",
    "RepositoryPathWorkspace",
]
