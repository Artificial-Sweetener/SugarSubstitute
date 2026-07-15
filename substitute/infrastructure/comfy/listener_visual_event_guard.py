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

"""Apply listener-scoped Substitute visual event identity checks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.infrastructure.comfy.cube_output_event import SubstituteVisualIdentity
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventContext,
    VisualEventRejectionDiagnostic,
    VisualEventRequestIdentity,
    substitute_visual_identity_rejection_reason,
    visual_event_rejection_diagnostic,
)


@dataclass(frozen=True)
class ListenerVisualEventGuard:
    """Validate visual event identity for a single listener run."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    client_id: str
    on_diagnostic: Callable[[VisualEventRejectionDiagnostic], None]

    def request_identity(self) -> VisualEventRequestIdentity:
        """Return the expected visual identity for this listener run."""

        return VisualEventRequestIdentity(
            workflow_id=self.workflow_id,
            generation_run_id=self.generation_run_id,
            prompt_id=self.prompt_id,
            client_id=self.client_id,
        )

    def context(
        self,
        *,
        event_type: str,
        node_id: str | None = None,
        display_node_id: str | None = None,
    ) -> VisualEventContext:
        """Return listener context shared by visual event diagnostics."""

        return VisualEventContext(
            workflow_id=self.workflow_id,
            generation_run_id=self.generation_run_id,
            prompt_id=self.prompt_id,
            client_id=self.client_id,
            event_type=event_type,
            node_id=node_id,
            display_node_id=display_node_id,
        )

    def accepts(
        self,
        identity: SubstituteVisualIdentity | None,
        *,
        prompt_id: str | None,
        event_type: str,
        node_id: str | None = None,
        display_node_id: str | None = None,
    ) -> bool:
        """Return whether a Backend visual identity belongs to this listener run."""

        event_context = self.context(
            event_type=event_type,
            node_id=node_id,
            display_node_id=display_node_id,
        )
        rejection_reason = substitute_visual_identity_rejection_reason(
            identity,
            self.request_identity(),
            prompt_id=prompt_id,
        )
        if rejection_reason is None:
            return True

        self.on_diagnostic(
            visual_event_rejection_diagnostic(
                rejection_reason,
                identity,
                event_context,
                event_prompt_id=prompt_id,
            )
        )
        return False


__all__ = ["ListenerVisualEventGuard"]
