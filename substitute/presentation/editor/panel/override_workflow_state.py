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

"""Own active-workflow override values, selections, and commands."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.overrides import (
    OverrideMap,
    OverrideParticipationSnapshot,
    OverrideSelectionMap,
    OverrideToolbarSnapshot,
    PinnedOverrideService,
)
from substitute.application.workflows.editor_projection_service import (
    WorkflowEditorProjection,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.editor.panel.overrides_controller")


def compact_override_log_value(value: Any) -> str:
    """Return a compact representation for structured override logging."""

    rendered = repr(value)
    return f"{rendered[:237]}..." if len(rendered) > 240 else rendered


class OverrideWorkflowState:
    """Own normalized override state for the active workflow."""

    def __init__(self, mainwindow: Any, service: PinnedOverrideService) -> None:
        """Store the shell workflow boundary and override domain service."""

        self._mainwindow = mainwindow
        self._service = service
        self.overrides: OverrideMap = {}
        self.selections: OverrideSelectionMap = {}

    def sync_from_workflow(self) -> None:
        """Load canonicalized override state from the active workflow."""

        workflow = self._mainwindow.get_active_workflow()
        workflow_id = getattr(
            getattr(self._mainwindow, "workflow_session_service", None),
            "active_workflow_id",
            None,
        )
        log_debug(
            _LOGGER,
            "global overrides sync from workflow started",
            workflow_id=workflow_id,
            workflow_present=workflow is not None,
            raw_override_keys=(
                tuple(
                    sorted(
                        str(key) for key in getattr(workflow, "global_overrides", {})
                    )
                )
                if workflow is not None
                else ()
            ),
        )
        if workflow is None:
            self.overrides = {}
            self.selections = {}
            return
        self.overrides = self._service.normalize_workflow_overrides(
            getattr(workflow, "global_overrides", None)
        )
        self.selections = self._service.normalize_workflow_selections(
            getattr(workflow, "global_override_selections", None)
        )
        log_debug(
            _LOGGER,
            "global overrides sync from workflow completed",
            workflow_id=workflow_id,
            normalized_overrides=tuple(
                {
                    "override_key": key,
                    "value": compact_override_log_value(value.get("value")),
                    "mode": value.get("mode"),
                }
                for key, value in sorted(self.overrides.items())
            ),
            normalized_selections=tuple(
                {"override_key": key, "selected": selected}
                for key, selected in sorted(self.selections.items())
            ),
        )
        self.sync_to_workflow()

    def materialize_defaults(
        self,
        *,
        behavior_snapshot: EditorBehaviorSnapshot | None,
        stack_order: tuple[str, ...],
    ) -> bool:
        """Materialize default-pinned values for the current workflow snapshot."""

        workflow = self._mainwindow.get_active_workflow()
        workflow_id = getattr(
            getattr(self._mainwindow, "workflow_session_service", None),
            "active_workflow_id",
            None,
        )
        log_debug(
            _LOGGER,
            "global overrides materialize defaults requested",
            workflow_id=workflow_id,
            workflow_present=workflow is not None,
            behavior_snapshot_present=behavior_snapshot is not None,
            existing_override_keys=tuple(sorted(self.overrides)),
            stack_order=stack_order,
        )
        if workflow is None or behavior_snapshot is None:
            return False
        changed = self._service.materialize_default_overrides(
            overrides=self.overrides,
            selections=self.selections,
            behavior_snapshot=behavior_snapshot,
            stack_order=stack_order,
        )
        if changed:
            self.sync_to_workflow()
        return changed

    def apply_to_projection(
        self,
        *,
        projection: WorkflowEditorProjection | None,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> bool:
        """Apply normalized overrides to the supplied editor projection."""

        return self._service.apply_overrides_to_projection(
            overrides=self.overrides,
            projection=projection,
            behavior_snapshot=behavior_snapshot,
        )

    def build_participation(
        self,
        *,
        behavior_snapshot: EditorBehaviorSnapshot,
        stack_order: tuple[str, ...],
    ) -> OverrideParticipationSnapshot:
        """Build field-level participation for current override values."""

        return self._service.build_participation_snapshot(
            overrides=self.overrides,
            behavior_snapshot=behavior_snapshot,
            stack_order=stack_order,
        )

    def build_serialization_scopes(
        self,
        *,
        behavior_snapshot: EditorBehaviorSnapshot,
        stack_order: tuple[str, ...],
    ) -> Mapping[str, object]:
        """Build SugarScript serialization scopes for current overrides."""

        return self._service.build_serialization_scopes(
            overrides=self.overrides,
            behavior_snapshot=behavior_snapshot,
            stack_order=stack_order,
        )

    def build_toolbar_snapshot(
        self,
        *,
        behavior_snapshot: EditorBehaviorSnapshot,
        stack_order: tuple[str, ...],
    ) -> OverrideToolbarSnapshot:
        """Build a semantic toolbar snapshot from current override values."""

        return self._service.build_toolbar_snapshot(
            behavior_snapshot=behavior_snapshot,
            stack_order=stack_order,
            overrides=self.overrides,
        )

    def is_selected(
        self,
        override_key: str,
        toolbar_snapshot: OverrideToolbarSnapshot | None,
    ) -> bool:
        """Return the effective authored menu selection for one key."""

        if override_key in self.selections:
            return self.selections[override_key]
        if toolbar_snapshot is None:
            return override_key in self.overrides
        return override_key in toolbar_snapshot.active_override_keys

    def toggle_from_action(
        self,
        action: Any,
        *,
        behavior_snapshot: EditorBehaviorSnapshot | None,
        stack_order: tuple[str, ...],
    ) -> bool:
        """Apply one override-menu toggle to workflow and local state."""

        workflow = self._mainwindow.get_active_workflow()
        if workflow is None or behavior_snapshot is None:
            return False
        data = action.data() or {}
        override_key = data.get("override_key")
        if not isinstance(override_key, str):
            return False
        workflow_overrides = self._service.normalize_workflow_overrides(
            getattr(workflow, "global_overrides", None)
        )
        workflow_selections = self._service.normalize_workflow_selections(
            getattr(workflow, "global_override_selections", None)
        )
        if bool(action.isChecked()):
            workflow_selections[override_key] = True
            changed = self._service.pin_override(
                overrides=workflow_overrides,
                behavior_snapshot=behavior_snapshot,
                stack_order=stack_order,
                override_key=override_key,
            )
        else:
            workflow_selections[override_key] = False
            changed = self._service.unpin_override(workflow_overrides, override_key)
        if not changed and getattr(workflow, "global_override_selections", {}) == dict(
            workflow_selections
        ):
            return False
        workflow.global_overrides = dict(workflow_overrides)
        workflow.global_override_selections = dict(workflow_selections)
        self.sync_from_workflow()
        return True

    def sync_to_workflow(self) -> None:
        """Persist current normalized state to the active workflow."""

        workflow = self._mainwindow.get_active_workflow()
        if workflow is None:
            return
        log_debug(
            _LOGGER,
            "syncing overrides to workflow",
            workflow_override_keys_before=tuple(
                sorted(str(key) for key in getattr(workflow, "global_overrides", {}))
            ),
            manager_overrides=tuple(
                {
                    "override_key": key,
                    "value": compact_override_log_value(value.get("value")),
                    "mode": value.get("mode"),
                }
                for key, value in sorted(self.overrides.items())
            ),
        )
        workflow.global_overrides = dict(self.overrides)
        workflow.global_override_selections = dict(self.selections)

    def clear(self) -> None:
        """Clear process-owned override state during manager teardown."""

        self.overrides.clear()
        self.selections.clear()


__all__ = ["OverrideWorkflowState", "compact_override_log_value"]
