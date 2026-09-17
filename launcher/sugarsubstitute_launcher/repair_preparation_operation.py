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

"""Compose cancellable preparation without moving native lifecycle ownership into Qt."""

from collections.abc import Callable
import logging
from uuid import uuid4

from launcher.sugarsubstitute_launcher.application.installation.models import (
    ReleaseManifestSource,
)
from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.preparation_progress import (
    PreparationProgress,
)
from launcher.sugarsubstitute_launcher.application.repair.preparation_service import (
    RepairPreparation,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.launcher_ui_process import (
    build_launcher_ui_command,
)
from launcher.sugarsubstitute_launcher.repair_preparation_invocation import (
    RepairPreparationInvocation,
)
from launcher.sugarsubstitute_launcher.repair_preparation_messages import (
    preparation_progress_from_message,
)
from launcher.sugarsubstitute_launcher.repair_preparation_result import (
    load_preparation_result,
)
from launcher.sugarsubstitute_launcher.repair_preparation_source import (
    RepairPreparationSource,
)
from launcher.sugarsubstitute_launcher.repair_process_supervisor import (
    RepairProcessSupervisor,
)
from sugarsubstitute_shared.windows_long_paths import operational_path, subprocess_path

_LOGGER = logging.getLogger(__name__)


class RepairPreparationOperation:
    """Own one transient input and delegate the complete child lifetime to its supervisor."""

    def __init__(
        self,
        *,
        layout: InstallLayout,
        release_source: ReleaseManifestSource,
        scope: RepairScope,
    ) -> None:
        """Capture the selected inputs without fetching release data or creating files."""
        self._layout = layout
        self._release_source = release_source
        self._scope = scope
        self._input_path = (
            operational_path(layout.root)
            / ".repair"
            / f"preparation-{uuid4().hex}.json"
        )
        self._input_created = False
        self._supervisor = RepairProcessSupervisor(
            command_builder=self._build_command,
            startup_log_path=layout.root
            / ".repair"
            / "diagnostics"
            / "repair-preparation.log",
        )

    @property
    def safe_to_close(self) -> bool:
        """Expose the native owner's verified cleanup state to the host."""
        return self._supervisor.safe_to_close

    def request_cancel(self) -> None:
        """Request cancellation without blocking the calling UI thread."""
        self._supervisor.request_cancel()

    def run(
        self, *, progress_observer: Callable[[PreparationProgress], None]
    ) -> RepairPreparation:
        """Stage in the child and return validated metadata only after native cleanup."""
        try:
            terminal = self._supervisor.run(
                progress_observer=lambda message: progress_observer(
                    preparation_progress_from_message(message)
                ),
                output_callback=self._output,
            )
            return load_preparation_result(
                terminal, layout=self._layout, scope=self._scope
            )
        finally:
            if self._input_created and self.safe_to_close:
                self._input_path.unlink(missing_ok=True)

    def _build_command(self) -> tuple[str, ...]:
        """Materialize input immediately before admission using the current launcher runtime."""
        self._input_path.parent.mkdir(parents=True, exist_ok=True)
        RepairPreparationInvocation(
            self._layout,
            RepairPreparationSource.capture(self._release_source),
            self._scope,
        ).save(self._input_path)
        self._input_created = True
        return build_launcher_ui_command(
            self._layout,
            (f"--repair-preparation-input={subprocess_path(self._input_path)}",),
        )

    @staticmethod
    def _output(line: str) -> None:
        """Retain child diagnostics without introducing another user-facing console owner."""
        _LOGGER.info("Repair preparation worker: %s", line)
