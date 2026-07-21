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

"""Adapt generic abuse actions to real-shell workflow and canvas lifecycle routes."""

from __future__ import annotations

from time import perf_counter

from tests.real_shell_prompt_editor_harness import (
    PromptFieldHandle,
    RealShellPromptEditorHarness,
)

from .models import PromptAbuseScenario
from .reorder_action_host import PromptReorderAbuseActionHost


class RealShellPromptAbuseActionHost(PromptReorderAbuseActionHost):
    """Own shell lifecycle actions that generic editor drivers cannot perform."""

    def __init__(
        self,
        harness: RealShellPromptEditorHarness,
        field: PromptFieldHandle,
    ) -> None:
        """Bind lifecycle actions to one mounted production prompt field."""

        super().__init__()
        self._harness = harness
        self._field = field

    def prepare_scenario(self, scenario: PromptAbuseScenario) -> None:
        """Prepare lifecycle fixtures before any measured action dispatch."""

        if any(action.kind == "workflow_round_trip" for action in scenario.actions):
            self._harness.prepare_workflow_round_trip(self._field)

    def workflow_round_trip(self) -> tuple[tuple[str, float], ...]:
        """Switch away and back while timing each visible workflow transition."""

        secondary_alias = self._harness.prepare_workflow_round_trip(self._field)
        started_at = perf_counter()
        self._harness.activate_workflow_for_trace(secondary_alias)
        away_ms = (perf_counter() - started_at) * 1_000.0
        started_at = perf_counter()
        self._harness.activate_workflow_for_trace(self._field.workflow.alias)
        returned_field = self._harness.prompt_field(self._field.workflow.alias)
        return_ms = (perf_counter() - started_at) * 1_000.0
        if returned_field.editor is not self._field.editor:
            raise RuntimeError("Workflow round trip replaced the measured editor.")
        self._field = returned_field
        return (("workflow:switch-away", away_ms), ("workflow:return", return_ms))

    def canvas_round_trip(self) -> tuple[tuple[str, float], ...]:
        """Switch away and back while timing each visible canvas transition."""

        started_at = perf_counter()
        self._harness.switch_canvas("Output")
        away_ms = (perf_counter() - started_at) * 1_000.0
        started_at = perf_counter()
        self._harness.switch_canvas("Input")
        self._harness.focus_editor(self._field)
        return_ms = (perf_counter() - started_at) * 1_000.0
        return (("canvas:switch-away", away_ms), ("canvas:return", return_ms))


__all__ = ["RealShellPromptAbuseActionHost"]
