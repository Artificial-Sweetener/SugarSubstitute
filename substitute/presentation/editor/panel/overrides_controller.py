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

"""Coordinate pinned workflow override controls in the shell toolbar."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import set_localized_tooltip

from collections.abc import Mapping
from inspect import signature
from typing import Any, cast

from PySide6.QtWidgets import QWidget

from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.display_labels import beautify_label
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.overrides import (
    OverrideParticipationSnapshot,
    PinnedOverrideControl,
    OverrideToolbarSnapshot,
    PinnedOverrideService,
)
from substitute.application.workflows.editor_projection_service import (
    WorkflowEditorProjection,
    WorkflowEditorProjectionService,
)
from substitute.application.ports import (
    NodeDefinitionGateway,
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.presentation.model_discovery import EmptyModelPickerAction
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.presentation.widgets.menu_model import MenuItem
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)
from substitute.presentation.editor.panel.override_control_interactions import (
    OverrideControlInteractionController,
)
from substitute.presentation.editor.panel.override_control_realizer import (
    OverrideControlRealizer,
)
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshotController,
)
from substitute.presentation.editor.panel.override_toolbar_registry import (
    OverrideToolbarRegistry,
)
from substitute.presentation.editor.panel.override_workflow_state import (
    OverrideWorkflowState,
    compact_override_log_value,
)
from substitute.shared.logging.logger import (
    log_debug,
    get_logger,
    log_warning,
)

_LOGGER = get_logger("presentation.editor.panel.overrides_controller")


def _accepts_named_parameter(callable_obj: Any, parameter_name: str) -> bool:
    """Return whether a callable explicitly advertises one named parameter."""

    try:
        parameters = signature(callable_obj).parameters
    except (TypeError, ValueError):
        return False
    return parameter_name in parameters


class GlobalOverridesManager:
    """Render the toolbar from pinned-override snapshots and forward user input."""

    def __init__(
        self,
        mainwindow: Any,
        *,
        pinned_override_service: PinnedOverrideService,
        node_definition_gateway: NodeDefinitionGateway,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        danbooru_url_import_service: DanbooruUrlImportService | None = None,
        danbooru_wiki_service: DanbooruWikiContentService | None = None,
        danbooru_image_preview_service: DanbooruImagePreviewService | None = None,
        danbooru_recent_posts_service: DanbooruRecentPostsService | None = None,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
        model_choice_snapshot_controller: PanelModelChoiceSnapshotController
        | None = None,
        thumbnail_asset_repository: ThumbnailAssetRepository | None = None,
        model_metadata_action_handler: ModelMetadataContextActionHandler | None = None,
        empty_model_picker_action: EmptyModelPickerAction | None = None,
        model_updates: ModelUpdatePickerBridge | None = None,
    ) -> None:
        """Initialize the toolbar renderer with explicit application dependencies."""

        self.mainwindow = mainwindow
        self._workflow_state = OverrideWorkflowState(
            mainwindow, pinned_override_service
        )
        self._global_override_menu: Any = None
        self.override_dropdown_btn: Any = None
        self._toolbar_registry = OverrideToolbarRegistry(
            mainwindow,
            lambda: self.override_dropdown_btn,
        )
        self._control_realizer = OverrideControlRealizer(
            parent=lambda: self.mainwindow.menu_bar,
            node_definition_gateway=node_definition_gateway,
            prompt_autocomplete_gateway=prompt_autocomplete_gateway,
            prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
            danbooru_url_import_service=danbooru_url_import_service,
            danbooru_wiki_service=danbooru_wiki_service,
            danbooru_image_preview_service=danbooru_image_preview_service,
            danbooru_recent_posts_service=danbooru_recent_posts_service,
            prompt_lora_catalog_service=prompt_lora_catalog_service,
            prompt_spellcheck_service=getattr(
                mainwindow,
                "prompt_spellcheck_service",
                None,
            ),
            model_choice_snapshot_controller=model_choice_snapshot_controller,
            thumbnail_asset_repository=thumbnail_asset_repository,
            model_metadata_action_handler=model_metadata_action_handler,
            empty_model_picker_action=empty_model_picker_action,
            model_updates=model_updates,
        )
        self._control_interactions = OverrideControlInteractionController(
            mainwindow,
            pinned_override_service,
            on_value_committed=self._refresh_after_value_commit,
            request_autosave=self._request_session_autosave,
        )
        self._toolbar_snapshot: OverrideToolbarSnapshot | None = None
        self._workflow_projection_service = WorkflowEditorProjectionService()

    def sync_state_from_workflow(self) -> None:
        """Load canonicalized override state from the active workflow."""

        self._workflow_state.sync_from_workflow()

    def materialize_default_overrides(self) -> bool:
        """Ensure default-pinned override values exist for the current workflow snapshot."""

        behavior_snapshot = self._current_behavior_snapshot()
        return self._workflow_state.materialize_defaults(
            behavior_snapshot=behavior_snapshot,
            stack_order=self._current_projection_order(),
        )

    def apply_global_overrides_without_snapshot_fallback(self) -> bool:
        """Apply persisted overrides before a behavior snapshot can be trusted."""

        workflow_present = self.mainwindow.get_active_workflow() is not None
        changed = self._workflow_state.apply_to_projection(
            projection=self._current_editor_projection(),
            behavior_snapshot=None,
        )
        log_debug(
            _LOGGER,
            "Applied global overrides without behavior snapshot",
            workflow_present=workflow_present,
            override_keys=tuple(sorted(self._workflow_state.overrides)),
            changed=changed,
        )
        return changed

    def rebuild_override_menu(self) -> None:
        """Rebuild the checkable override menu from the current toolbar snapshot."""

        toolbar_snapshot = self._refresh_toolbar_snapshot()
        if self._global_override_menu is None:
            return
        self._global_override_menu.clear()

        entries = tuple(
            MenuItem(
                f"global_override.{candidate.override_key}",
                beautify_label(candidate.label),
                checkable=True,
                checked=self._is_override_selected(candidate.override_key),
                data={"override_key": candidate.override_key},
            )
            for candidate in toolbar_snapshot.candidates
        )
        QFluentMenuRenderer(
            parent=cast(QWidget, self._global_override_menu)
        ).populate_menu(
            self._global_override_menu,
            entries,
        )

        if self.override_dropdown_btn is not None:
            set_localized_tooltip(self.override_dropdown_btn, "Set Global Override")

    def rebuild_active_override_controls(self) -> None:
        """Rebuild active toolbar controls from the latest toolbar snapshot."""

        if self._toolbar_overrides_suppressed_for_route():
            self.clear_toolbar_override_controls()
            return
        toolbar_snapshot = self._refresh_toolbar_snapshot()
        log_debug(
            _LOGGER,
            "rebuilding active override controls started",
            active_override_keys=toolbar_snapshot.active_override_keys,
            existing_control_keys=tuple(sorted(self._toolbar_registry.controls)),
            active_controls=tuple(
                {
                    "override_key": control.override_key,
                    "value": compact_override_log_value(control.value),
                    "representative_cube": control.spec.cube_alias,
                    "representative_node": control.spec.node_name,
                    "representative_class": control.spec.class_type,
                    "representative_field": control.spec.field_key,
                    "spec_value": compact_override_log_value(control.spec.value),
                    "spec_raw_value": compact_override_log_value(
                        control.spec.raw_value
                    ),
                    "spec_value_source": control.spec.value_source.value,
                }
                for control in toolbar_snapshot.active_controls
            ),
        )
        active_by_key = {
            control.override_key: control
            for control in toolbar_snapshot.active_controls
        }
        active_signature = tuple(
            self._control_realizer.signature(control)
            for control in toolbar_snapshot.active_controls
        )
        active_keys_unchanged = tuple(sorted(self._toolbar_registry.controls)) == tuple(
            sorted(active_by_key)
        )
        if (
            self._toolbar_registry.active_signature == active_signature
            and active_keys_unchanged
            and self._toolbar_registry.all_attached(active_by_key)
        ):
            self._normalize_existing_override_controls(active_by_key)
            self._refresh_restart_toolbar_spacing()
            return
        reused_count = 0
        created_count = 0
        removed_count = 0
        replaced_count = 0

        for override_key in list(self._toolbar_registry.controls):
            if override_key not in active_by_key:
                if self._toolbar_registry.remove(override_key):
                    removed_count += 1

        for control in toolbar_snapshot.active_controls:
            signature = self._control_realizer.signature(control)
            existing_control = self._toolbar_registry.control(control.override_key)
            existing_signature = self._toolbar_registry.control_signature(
                control.override_key
            )
            if existing_control is not None and existing_signature == signature:
                label_widget, widget = existing_control
                self._control_realizer.normalize(
                    active_by_key[control.override_key],
                    label_widget,
                    widget,
                )
                self._toolbar_registry.insert(
                    override_key=control.override_key,
                    label_widget=label_widget,
                    widget=widget,
                    active_keys=toolbar_snapshot.active_override_keys,
                )
                reused_count += 1
                continue
            if existing_control is not None:
                self._toolbar_registry.remove(control.override_key)
                replaced_count += 1
            if self._create_override_widget(control.override_key):
                created_count += 1
        log_debug(
            _LOGGER,
            "Rebuilt active override controls",
            reused_count=reused_count,
            created_count=created_count,
            removed_count=removed_count,
            replaced_count=replaced_count,
            active_control_count=len(toolbar_snapshot.active_controls),
        )
        self._toolbar_registry.active_signature = active_signature
        self._refresh_restart_toolbar_spacing()

    def apply_global_overrides(
        self,
        *,
        use_cached_behavior_snapshot: bool = False,
    ) -> None:
        """Apply active workflow overrides to buffers and refresh hidden-field state."""

        workflow = self.mainwindow.get_active_workflow()
        behavior_snapshot = self._current_behavior_snapshot()
        workflow_id = getattr(
            getattr(self.mainwindow, "workflow_session_service", None),
            "active_workflow_id",
            None,
        )
        log_debug(
            _LOGGER,
            "global overrides apply requested",
            workflow_id=workflow_id,
            workflow_present=workflow is not None,
            behavior_snapshot_present=behavior_snapshot is not None,
            override_keys=tuple(sorted(self._workflow_state.overrides)),
            overrides=tuple(
                {
                    "override_key": key,
                    "value": compact_override_log_value(value.get("value")),
                    "mode": value.get("mode"),
                }
                for key, value in sorted(self._workflow_state.overrides.items())
            ),
        )
        overrides_changed = self._workflow_state.apply_to_projection(
            projection=self._current_editor_projection(),
            behavior_snapshot=behavior_snapshot,
        )
        override_hidden_field_keys = self._override_hidden_field_keys(behavior_snapshot)

        panel = self.mainwindow.active_editor_panel
        if panel is None:
            return
        if hasattr(panel, "refresh_node_behavior_state"):
            try:
                refresh = panel.refresh_node_behavior_state
                refresh_kwargs: dict[str, object] = {
                    "reason": "global_override_changed",
                    "use_cached_snapshot": (
                        use_cached_behavior_snapshot and not overrides_changed
                    ),
                }
                if _accepts_named_parameter(refresh, "override_hidden_field_keys"):
                    refresh_kwargs["override_hidden_field_keys"] = (
                        override_hidden_field_keys
                    )
                refresh(**refresh_kwargs)
                return
            except Exception as error:
                log_warning(
                    _LOGGER,
                    "Pinned override refresh fallback triggered",
                    error_type=type(error).__name__,
                )
        fallback_hidden = self._fallback_hidden_field_keys(behavior_snapshot)
        if hasattr(panel, "set_hidden_field_keys"):
            panel.set_hidden_field_keys(fallback_hidden)

    def current_participation_snapshot(
        self,
    ) -> OverrideParticipationSnapshot | None:
        """Return current field-level global override participation when available."""

        workflow = self.mainwindow.get_active_workflow()
        behavior_snapshot = self._current_behavior_snapshot()
        if workflow is None or behavior_snapshot is None:
            return None
        return self._workflow_state.build_participation(
            behavior_snapshot=behavior_snapshot,
            stack_order=self._current_projection_order(),
        )

    def current_serialization_scopes(
        self,
    ) -> Mapping[str, object] | None:
        """Return active SugarScript serialization scopes when context is available."""

        workflow = self.mainwindow.get_active_workflow()
        behavior_snapshot = self._current_behavior_snapshot()
        if workflow is None or behavior_snapshot is None:
            return None
        return self._workflow_state.build_serialization_scopes(
            behavior_snapshot=behavior_snapshot,
            stack_order=self._current_projection_order(),
        )

    def _override_hidden_field_keys(
        self,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> set[object]:
        """Return hidden field tuples for currently participating global overrides."""

        workflow = self.mainwindow.get_active_workflow()
        if workflow is None or behavior_snapshot is None:
            return set()
        participation = self._workflow_state.build_participation(
            behavior_snapshot=behavior_snapshot,
            stack_order=self._current_projection_order(),
        )
        return set(participation.participant_fields())

    def project_seed_value_from_workflow(self, value: int) -> None:
        """Project the authoritative override seed without emitting user intent."""

        self.sync_state_from_workflow()
        control = self._toolbar_registry.control("seed")
        if control is None:
            return
        _label, widget = control
        self._control_interactions.project_seed_value(widget, value)

    def dispose(self) -> None:
        """Tear down toolbar widgets and clear in-memory override state."""

        try:
            self._toolbar_registry.clear()
        finally:
            self._workflow_state.clear()
            self._toolbar_snapshot = None

    def _on_override_menu_toggled(self, action: Any) -> None:
        """Handle checked and unchecked actions from the overrides drop-down menu."""

        behavior_snapshot = self._current_behavior_snapshot()
        if self._workflow_state.toggle_from_action(
            action,
            behavior_snapshot=behavior_snapshot,
            stack_order=self._current_projection_order(),
        ):
            self._refresh_toolbar_after_toggle()
        self._request_session_autosave()

    def _refresh_toolbar_after_toggle(self) -> None:
        """Rebuild local toolbar state after one menu toggle without repinning defaults."""

        self.rebuild_override_menu()
        self.rebuild_active_override_controls()
        self.apply_global_overrides()

    def _sync_overrides_to_workflow(self) -> None:
        """Persist current manager override state to the active workflow."""

        self._workflow_state.sync_to_workflow()

    def _refresh_toolbar_snapshot(self) -> OverrideToolbarSnapshot:
        """Build and cache the latest toolbar snapshot from the editor behavior snapshot."""

        workflow = self.mainwindow.get_active_workflow()
        behavior_snapshot = self._current_behavior_snapshot()
        log_debug(
            _LOGGER,
            "refresh toolbar snapshot requested",
            workflow_present=workflow is not None,
            behavior_snapshot_present=behavior_snapshot is not None,
            stack_order=self._current_projection_order(),
            override_keys=tuple(sorted(self._workflow_state.overrides)),
        )
        if workflow is None or behavior_snapshot is None:
            self._toolbar_snapshot = OverrideToolbarSnapshot([], [], ())
            return self._toolbar_snapshot
        self._toolbar_snapshot = self._workflow_state.build_toolbar_snapshot(
            behavior_snapshot=behavior_snapshot,
            stack_order=self._current_projection_order(),
        )
        log_debug(
            _LOGGER,
            "refresh toolbar snapshot completed",
            candidate_count=len(self._toolbar_snapshot.candidates),
            active_control_count=len(self._toolbar_snapshot.active_controls),
            active_override_keys=self._toolbar_snapshot.active_override_keys,
        )
        return self._toolbar_snapshot

    def _is_override_selected(self, override_key: str) -> bool:
        """Return the effective authored menu selection for one override key."""

        return self._workflow_state.is_selected(override_key, self._toolbar_snapshot)

    def _current_behavior_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Return the latest application-owned editor behavior snapshot when available."""

        panel = self.mainwindow.active_editor_panel
        if panel is None:
            return None
        if hasattr(panel, "current_behavior_snapshot"):
            snapshot = panel.current_behavior_snapshot()
            return snapshot if isinstance(snapshot, EditorBehaviorSnapshot) else None
        snapshot = getattr(panel, "_last_behavior_snapshot", None)
        return snapshot if isinstance(snapshot, EditorBehaviorSnapshot) else None

    def _current_editor_projection(self) -> WorkflowEditorProjection | None:
        """Return the unified graph-state projection for the active document."""

        workflow = self.mainwindow.get_active_workflow()
        if workflow is None:
            return None
        return self._workflow_projection_service.project(workflow)

    def _current_projection_order(self) -> tuple[str, ...]:
        """Return the active editor section order for override discovery."""

        projection = self._current_editor_projection()
        return projection.order if projection is not None else ()

    def detach_override_widgets(self) -> None:
        """Detach cached toolbar controls from the shared menu bar without disposal."""

        self._toolbar_registry.detach()

    def clear_toolbar_override_controls(self) -> None:
        """Detach all workflow override controls from the shared toolbar."""

        self._toolbar_registry.clear()

    def mounted_control_count(self) -> int:
        """Return the number of realized toolbar override controls."""

        return len(self._toolbar_registry.controls)

    def _normalize_existing_override_controls(
        self,
        active_by_key: dict[str, PinnedOverrideControl],
    ) -> None:
        """Reapply toolbar sizing to cached controls before reuse shortcuts return."""

        for override_key, control in active_by_key.items():
            existing_control = self._toolbar_registry.control(override_key)
            if existing_control is None:
                continue
            label_widget, widget = existing_control
            self._control_realizer.normalize(control, label_widget, widget)

    def _refresh_restart_toolbar_spacing(self) -> None:
        """Ask the restart toolbar control to absorb slack after override changes."""

        refresh = getattr(
            getattr(self.mainwindow, "pendingRestartButton", None),
            "refresh_toolbar_spacing",
            None,
        )
        if callable(refresh):
            refresh()

    def _toolbar_overrides_suppressed_for_route(self) -> bool:
        """Return whether the current shell route forbids workflow override chrome."""

        return (
            getattr(self.mainwindow, "_active_workspace_route", None)
            == SETTINGS_WORKSPACE_ROUTE
        )

    def _create_override_widget(self, override_key: str) -> bool:
        """Create one toolbar control from the current pinned override snapshot."""

        toolbar_snapshot = self._toolbar_snapshot or self._refresh_toolbar_snapshot()
        control = next(
            (
                candidate
                for candidate in toolbar_snapshot.active_controls
                if candidate.override_key == override_key
            ),
            None,
        )
        if control is None:
            return False
        realization = self._control_realizer.realize(control)
        if realization is None:
            return False
        label_widget = realization.label_widget
        widget = realization.widget

        self._toolbar_registry.insert(
            override_key=control.override_key,
            label_widget=label_widget,
            widget=widget,
            active_keys=toolbar_snapshot.active_override_keys,
        )
        self._toolbar_registry.register(
            control.override_key,
            label_widget,
            widget,
            realization.signature,
        )

        self._control_interactions.bind(control.override_key, widget)
        return True

    def _refresh_after_value_commit(self) -> None:
        """Refresh workflow state and mounted fields after a toolbar value commit."""

        self.sync_state_from_workflow()
        self.apply_global_overrides()

    def _request_session_autosave(self) -> None:
        """Request persistence after one user-owned override mutation."""

        request_autosave = getattr(self.mainwindow, "request_session_autosave", None)
        if callable(request_autosave):
            request_autosave()

    def _fallback_hidden_field_keys(
        self,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> set[object]:
        """Return conservative hidden-field keys when unified recompute is unavailable."""

        if behavior_snapshot is None:
            return set()
        return self._override_hidden_field_keys(behavior_snapshot)


__all__ = ["GlobalOverridesManager"]
