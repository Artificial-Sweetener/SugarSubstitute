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

"""Inspect production prompt-workflow rendering and segment state."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QWidget
from sugarsubstitute_shared.presentation.localization import render_application_text
from tests.support.prompt_editor.real_shell.models import (
    PromptFieldHandle,
    PromptSegmentDialogProbe,
    PromptSegmentScopeProbe,
)
from tests.support.prompt_editor.real_shell.session import PromptEditorRealShell


class PromptWorkflowProbes:
    """Read mounted workflow presentation state without changing it."""

    def __init__(self, shell: PromptEditorRealShell) -> None:
        """Bind probes to the mounted real-shell session."""

        self._shell = shell

    def rendered_node_card_order(
        self,
        field: PromptFieldHandle,
    ) -> tuple[str, ...]:
        """Return production masonry insertion order for one cube section."""

        ancestor: QWidget | None = field.editor
        while ancestor is not None:
            node_card_order = getattr(ancestor, "node_card_order", None)
            if callable(node_card_order):
                return tuple(node_card_order())
            ancestor = ancestor.parentWidget()
        raise AssertionError("cube masonry owner is unavailable")

    def probe_prompt_segment_scopes(
        self,
        field: PromptFieldHandle,
    ) -> PromptSegmentScopeProbe:
        """Capture model and segment state without refreshing either owner."""

        panel = self._shell.editor_panels[field.workflow.workflow_id]
        candidate = panel.active_model_context_controller.current_model()
        active_snapshot = panel.active_model_snapshot_controller.snapshot
        segment_controller = cast(Any, field.editor)._segment_preset_controller
        editor_snapshot = segment_controller.snapshot
        scopes = editor_snapshot.save_state.save_scopes
        return PromptSegmentScopeProbe(
            candidate_kind=None if candidate is None else candidate.model_kind,
            candidate_value=None if candidate is None else candidate.value,
            active_snapshot_readiness=active_snapshot.status.readiness.value,
            active_snapshot_reason=active_snapshot.status.unavailable_reason,
            active_snapshot_item_value=(
                None
                if active_snapshot.catalog_item is None
                else active_snapshot.catalog_item.backend_value
            ),
            active_snapshot_family_labels=tuple(
                association.label for association in active_snapshot.family_associations
            ),
            editor_snapshot_readiness=editor_snapshot.status.readiness.value,
            editor_snapshot_reason=editor_snapshot.status.unavailable_reason,
            editor_scope_titles=tuple(
                render_application_text(scope.title) for scope in scopes
            ),
            editor_scope_full_labels=tuple(
                render_application_text(scope.full_label) for scope in scopes
            ),
        )

    def probe_prompt_segment_dialog(
        self,
        field: PromptFieldHandle,
        *,
        selected_text: str,
    ) -> PromptSegmentDialogProbe:
        """Capture the production save request without displaying a modal dialog."""

        requests: list[object] = []

        def capture_request(request: object) -> None:
            """Record one dialog request and simulate cancellation."""

            requests.append(request)
            return None

        controller = cast(Any, field.editor)._segment_preset_controller
        controller.save_selected_segment_as_preset(
            selected_text,
            dialog_runner=capture_request,
        )
        if len(requests) != 1:
            raise AssertionError(
                f"expected one dialog request, received {len(requests)}"
            )
        request = cast(Any, requests[0])
        return PromptSegmentDialogProbe(
            title=render_application_text(request.title),
            selected_text=str(request.selected_text),
            scope_titles=tuple(
                render_application_text(scope.title) for scope in request.scopes
            ),
            scope_full_labels=tuple(
                render_application_text(scope.full_label) for scope in request.scopes
            ),
        )
