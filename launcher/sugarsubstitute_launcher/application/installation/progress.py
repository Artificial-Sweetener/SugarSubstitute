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

"""Report installation milestones without granting presentation transaction ownership."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
import logging


_LOGGER = logging.getLogger(__name__)


class InstallationStage(IntEnum):
    """Order the installer's work before the application's separate setup journey."""

    PREPARATION = 0
    APPLICATION = 1
    RUNTIME = 2
    HANDOFF = 3


@dataclass(frozen=True, slots=True)
class InstallationProgress:
    """Identify a real stage boundary; completion is a stage estimate, not time."""

    stage: InstallationStage
    finished: bool = False

    @property
    def completed(self) -> int:
        """Return how many installation stages have returned successfully."""
        return int(self.stage) + int(self.finished)

    @property
    def total(self) -> int:
        """Return the installer-owned stages, excluding subsequent Comfy setup."""
        return len(InstallationStage)


InstallationProgressObserver = Callable[[InstallationProgress], None]


class InstallationProgressReporter:
    """Isolate optional feedback failures from installation and process handoff."""

    def __init__(self, observer: InstallationProgressObserver | None) -> None:
        """Bind one workflow's optional presentation observer."""
        self._observer = observer

    def publish(self, stage: InstallationStage, *, finished: bool = False) -> None:
        """Publish an authoritative boundary and disable failed feedback once."""
        if self._observer is None:
            return
        try:
            self._observer(InstallationProgress(stage, finished))
        except Exception:
            _LOGGER.exception(
                "Installation progress observer failed; continuing installation.",
                extra={"installation_stage": stage.name, "stage_finished": finished},
            )
            self._observer = None
