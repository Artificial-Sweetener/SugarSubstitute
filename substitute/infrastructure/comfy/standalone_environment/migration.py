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

"""Promote an extracted standalone bundle into the managed workspace layout."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from substitute.infrastructure.comfy.standalone_environment.layout import (
    ExtractedStandaloneLayout,
    ManagedStandaloneLayout,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArtifactError,
    StandaloneEnvironmentRelease,
)


class StandaloneWorkspaceMigrator:
    """Own the one-time layout transformation for a new managed workspace."""

    def promote(
        self,
        extracted_root: Path,
        workspace: Path,
        release: StandaloneEnvironmentRelease,
    ) -> ManagedStandaloneLayout:
        """Atomically promote upstream ComfyUI and retain its master environment."""

        extracted = ExtractedStandaloneLayout(extracted_root)
        extracted.validate(release)
        self._require_empty_target(workspace)
        workspace.parent.mkdir(parents=True, exist_ok=True)
        prepared = workspace.with_name(
            f".{workspace.name}.standalone-next-{uuid4().hex}"
        )
        try:
            extracted.comfyui.replace(prepared)
            extracted.master_environment.replace(prepared / ".standalone-env")
            metadata_dir = prepared / ".substitute"
            metadata_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                extracted.manifest,
                metadata_dir / "standalone-environment.json",
            )
            if workspace.exists():
                workspace.rmdir()
            prepared.replace(workspace)
        except OSError as error:
            shutil.rmtree(prepared, ignore_errors=True)
            raise StandaloneArtifactError(
                f"Could not promote standalone environment into {workspace}: {error}"
            ) from error
        finally:
            shutil.rmtree(extracted_root, ignore_errors=True)
        return ManagedStandaloneLayout(workspace, release.variant)

    def _require_empty_target(self, workspace: Path) -> None:
        """Reject promotion over user files or an existing Comfy workspace."""

        if not workspace.exists():
            return
        if not workspace.is_dir() or any(workspace.iterdir()):
            raise StandaloneArtifactError(
                f"Managed workspace must be empty before promotion: {workspace}"
            )
