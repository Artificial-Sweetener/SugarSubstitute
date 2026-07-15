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

"""Compose projection source-state owners for the prompt projection surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QObject

from .freshness_controller import PromptProjectionFreshnessController
from .incremental_apply_controller import (
    PromptProjectionIncrementalApplyController,
    PromptProjectionIncrementalApplyHost,
)
from .prompt_state_applier import (
    PromptProjectionPromptStateApplier,
    PromptProjectionPromptStateHost,
)
from .source_change_applier import PromptProjectionSourceChangeApplier
from .source_document import PromptProjectionSourceDocument
from .transient_edit_overlays import PromptProjectionTransientEditOverlayController
from .update_scheduler import PendingProjectionUpdate


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceStateOwners:
    """Carry the source-state owners extracted from the projection surface."""

    source_document: PromptProjectionSourceDocument
    source_change_applier: PromptProjectionSourceChangeApplier[object]
    transient_edit_overlays: PromptProjectionTransientEditOverlayController
    freshness_controller: PromptProjectionFreshnessController
    incremental_apply_controller: PromptProjectionIncrementalApplyController
    prompt_state_applier: PromptProjectionPromptStateApplier


class _PromptProjectionScheduledUpdateSink:
    """Forward scheduled projection updates after the prompt-state owner exists."""

    def __init__(self) -> None:
        """Create an unwired scheduled update sink."""

        self._applier: PromptProjectionPromptStateApplier | None = None

    def wire(self, applier: PromptProjectionPromptStateApplier) -> None:
        """Attach the prompt-state applier after owner construction."""

        self._applier = applier

    def apply_update(self, update: PendingProjectionUpdate) -> None:
        """Apply one scheduled update through the prompt-state owner."""

        if self._applier is None:
            raise RuntimeError("Prompt projection prompt-state applier is not wired.")
        self._applier.apply_scheduled_projection_update(update)


def build_prompt_projection_source_state_owners(
    host: object,
    *,
    parent: QObject,
) -> PromptProjectionSourceStateOwners:
    """Build projection source-state owners around a viewport/paint host."""

    scheduled_update_sink = _PromptProjectionScheduledUpdateSink()
    source_document = PromptProjectionSourceDocument(parent=parent)
    transient_edit_overlays = PromptProjectionTransientEditOverlayController()
    freshness_controller = PromptProjectionFreshnessController(
        apply_update=scheduled_update_sink.apply_update,
        parent=parent,
    )
    incremental_apply_controller = PromptProjectionIncrementalApplyController(
        cast(PromptProjectionIncrementalApplyHost, host)
    )
    prompt_state_applier = PromptProjectionPromptStateApplier(
        cast(PromptProjectionPromptStateHost, host)
    )
    scheduled_update_sink.wire(prompt_state_applier)
    source_change_applier = PromptProjectionSourceChangeApplier[object](host)
    return PromptProjectionSourceStateOwners(
        source_document=source_document,
        source_change_applier=source_change_applier,
        transient_edit_overlays=transient_edit_overlays,
        freshness_controller=freshness_controller,
        incremental_apply_controller=incremental_apply_controller,
        prompt_state_applier=prompt_state_applier,
    )


__all__ = [
    "PromptProjectionSourceStateOwners",
    "build_prompt_projection_source_state_owners",
]
