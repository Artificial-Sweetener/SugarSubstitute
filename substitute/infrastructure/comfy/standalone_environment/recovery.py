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

"""Resume interrupted owned standalone hydration before runtime reconciliation."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess

from substitute.infrastructure.comfy.standalone_environment.environment_builder import (
    StandaloneVirtualEnvironmentBuilder,
)
from substitute.infrastructure.comfy.standalone_environment.hydration_state import (
    StandaloneHydrationState,
)
from substitute.infrastructure.comfy.standalone_environment.layout import (
    ManagedStandaloneLayout,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArtifactError,
    StandaloneVariantId,
)


_LOGGER = logging.getLogger(__name__)
_LEGACY_BOOTSTRAP_PROBE = "from packaging.requirements import Requirement"


class StandaloneEnvironmentRecovery:
    """Recover only runtimes carrying the standalone producer's ownership manifest."""

    def __init__(
        self, *, builder: StandaloneVirtualEnvironmentBuilder | None = None
    ) -> None:
        """Retain the same hydration owner used for new installations."""

        self._builder = builder or StandaloneVirtualEnvironmentBuilder()

    def resume(self, workspace: Path) -> bool:
        """Resume incomplete hydration without replacing Comfy or its user files.

        Pre-transaction installations retain their environment when it can run
        the requirements parser needed by existing-workspace reconciliation.
        New transactions derive readiness solely from their durable phase.
        """

        manifest_path = workspace / ".substitute" / "standalone-environment.json"
        if not manifest_path.is_file():
            return False
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("Standalone manifest must be an object.")
            variant = StandaloneVariantId(manifest["id"])
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise StandaloneArtifactError(
                "Cannot verify ownership of the standalone Python environment."
            ) from error
        layout = ManagedStandaloneLayout(workspace, variant)
        state = StandaloneHydrationState(workspace)
        if not state.incomplete and layout.virtual_python.is_file():
            if state.recorded or self._legacy_runtime_can_reconcile(layout):
                return False
        layout.validate_master()
        _LOGGER.warning("Resuming interrupted standalone Python hydration")
        self._builder.build(layout)
        return True

    @staticmethod
    def _legacy_runtime_can_reconcile(layout: ManagedStandaloneLayout) -> bool:
        """Preserve usable legacy environments without trusting executable presence."""

        try:
            result = subprocess.run(
                [str(layout.virtual_python), "-I", "-c", _LEGACY_BOOTSTRAP_PROBE],
                cwd=layout.workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
                creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
            )
        except (OSError, subprocess.SubprocessError):
            _LOGGER.exception(
                "Legacy standalone runtime could not run its bootstrap probe"
            )
            return False
        if result.returncode:
            _LOGGER.warning(
                "Legacy standalone runtime cannot reconcile dependencies | exit_code=%s | detail=%s",
                result.returncode,
                result.stderr.strip(),
            )
            return False
        return True
