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

from collections.abc import Mapping
from functools import partial
from inspect import signature
from typing import Any, cast

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QSizePolicy, QWidget
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]

from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.display_labels import beautify_label
from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldPresentation,
    ResolvedFieldSpec,
    is_choice_field_type,
)
from substitute.application.overrides import (
    OverrideMap,
    OverrideParticipationSnapshot,
    OverrideSelectionMap,
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
from substitute.domain.generation.seed_control import (
    SeedControlState,
    SeedMode,
    seed_mode_from_value,
)
from substitute.application.prompt_editor import PromptLoraCatalogLookup
from substitute.application.model_metadata import (
    ThumbnailAssetRepository,
    model_kind_for_field,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.presentation.widgets.menu_model import MenuItem
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)
from substitute.presentation.editor.panel.factories.choice_factory import (
    resolve_choice_options_for_field,
)
from substitute.presentation.editor.panel.factories.field_pipeline import (
    LAYOUT_HANDLED,
    build_widget_for_field_spec,
)
from substitute.presentation.editor.panel.factories.field_build_outcome import (
    EditorFieldBuildKind,
)
from substitute.presentation.editor.panel.factories.field_build_resolver import (
    resolve_editor_field_build,
)
from substitute.presentation.editor.panel.override_control_binding import (
    bind_override_control,
)
from substitute.presentation.editor.panel.override_control_identity import (
    identify_override_surface,
)
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshotController,
)
from substitute.shared.logging.logger import (
    log_debug,
    get_logger,
    log_warning,
    log_warning_exception,
)

_LOGGER = get_logger("presentation.editor.panel.overrides_controller")
_TOOLBAR_MAX_WIDGET_WIDTH = 180
_TOOLBAR_CONTROL_HEIGHT = 32


def _compact_log_value(value: Any) -> str:
    """Return a compact representation for structured override logging."""

    rendered = repr(value)
    if len(rendered) > 240:
        return f"{rendered[:237]}..."
    return rendered


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
    ) -> None:
        """Initialize the toolbar renderer with explicit application dependencies."""

        self.mainwindow = mainwindow
        self._service = pinned_override_service
        self._node_definition_gateway = node_definition_gateway
        self._prompt_autocomplete_gateway = prompt_autocomplete_gateway
        self._prompt_wildcard_catalog_gateway = prompt_wildcard_catalog_gateway
        self._danbooru_url_import_service = danbooru_url_import_service
        self._danbooru_wiki_service = danbooru_wiki_service
        self._danbooru_image_preview_service = danbooru_image_preview_service
        self._danbooru_recent_posts_service = danbooru_recent_posts_service
        self._prompt_lora_catalog_service = prompt_lora_catalog_service
        self._model_choice_snapshot_controller = model_choice_snapshot_controller
        self._thumbnail_asset_repository = thumbnail_asset_repository
        self._model_metadata_action_handler = model_metadata_action_handler
        self._global_overrides: OverrideMap = {}
        self._global_override_selections: OverrideSelectionMap = {}
        self._global_override_controls: dict[str, tuple[Any, Any]] = {}
        self._global_override_control_signatures: dict[
            str,
            tuple[object, ...],
        ] = {}
        self._active_controls_signature: tuple[tuple[object, ...], ...] | None = None
        self._global_override_menu: Any = None
        self.override_dropdown_btn: Any = None
        self._toolbar_snapshot: OverrideToolbarSnapshot | None = None
        self._workflow_projection_service = WorkflowEditorProjectionService()

    def sync_state_from_workflow(self) -> None:
        """Load canonicalized override state from the active workflow."""

        workflow = self.mainwindow.get_active_workflow()
        workflow_id = getattr(
            getattr(self.mainwindow, "workflow_session_service", None),
            "active_workflow_id",
            None,
        )
        log_debug(
            _LOGGER,
            "global overrides sync from workflow started",
            workflow_id=workflow_id,
            workflow_present=workflow is not None,
            raw_override_keys=tuple(
                sorted(str(key) for key in getattr(workflow, "global_overrides", {}))
            )
            if workflow is not None
            else (),
        )
        if workflow is None:
            self._global_overrides = {}
            self._global_override_selections = {}
            return
        self._global_overrides = self._service.normalize_workflow_overrides(
            getattr(workflow, "global_overrides", None)
        )
        self._global_override_selections = self._service.normalize_workflow_selections(
            getattr(workflow, "global_override_selections", None)
        )
        log_debug(
            _LOGGER,
            "global overrides sync from workflow completed",
            workflow_id=workflow_id,
            normalized_overrides=tuple(
                {
                    "override_key": key,
                    "value": _compact_log_value(value.get("value")),
                    "mode": value.get("mode"),
                }
                for key, value in sorted(self._global_overrides.items())
            ),
            normalized_selections=tuple(
                {
                    "override_key": key,
                    "selected": selected,
                }
                for key, selected in sorted(self._global_override_selections.items())
            ),
        )
        self._sync_overrides_to_workflow()

    def materialize_default_overrides(self) -> bool:
        """Ensure default-pinned override values exist for the current workflow snapshot."""

        workflow = self.mainwindow.get_active_workflow()
        behavior_snapshot = self._current_behavior_snapshot()
        workflow_id = getattr(
            getattr(self.mainwindow, "workflow_session_service", None),
            "active_workflow_id",
            None,
        )
        log_debug(
            _LOGGER,
            "global overrides materialize defaults requested",
            workflow_id=workflow_id,
            workflow_present=workflow is not None,
            behavior_snapshot_present=behavior_snapshot is not None,
            existing_override_keys=tuple(sorted(self._global_overrides)),
            stack_order=self._current_projection_order(),
        )
        if workflow is None or behavior_snapshot is None:
            return False
        if self._service.materialize_default_overrides(
            overrides=self._global_overrides,
            selections=self._global_override_selections,
            behavior_snapshot=behavior_snapshot,
            stack_order=self._current_projection_order(),
        ):
            self._sync_overrides_to_workflow()
            return True
        return False

    def apply_global_overrides_without_snapshot_fallback(self) -> bool:
        """Apply persisted overrides before a behavior snapshot can be trusted."""

        workflow = self.mainwindow.get_active_workflow()
        changed = self._service.apply_overrides_to_projection(
            overrides=self._global_overrides,
            projection=self._current_editor_projection(),
            behavior_snapshot=None,
        )
        log_debug(
            _LOGGER,
            "Applied global overrides without behavior snapshot",
            workflow_present=workflow is not None,
            override_keys=tuple(sorted(self._global_overrides)),
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
            self.override_dropdown_btn.setToolTip("Set Global Override")

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
            existing_control_keys=tuple(sorted(self._global_override_controls)),
            active_controls=tuple(
                {
                    "override_key": control.override_key,
                    "value": _compact_log_value(control.value),
                    "representative_cube": control.spec.cube_alias,
                    "representative_node": control.spec.node_name,
                    "representative_class": control.spec.class_type,
                    "representative_field": control.spec.field_key,
                    "spec_value": _compact_log_value(control.spec.value),
                    "spec_raw_value": _compact_log_value(control.spec.raw_value),
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
            self._override_control_signature(control)
            for control in toolbar_snapshot.active_controls
        )
        active_keys_unchanged = tuple(sorted(self._global_override_controls)) == tuple(
            sorted(active_by_key)
        )
        if (
            self._active_controls_signature == active_signature
            and active_keys_unchanged
            and self._active_override_controls_attached(active_by_key)
        ):
            self._normalize_existing_override_controls(active_by_key)
            self._refresh_restart_toolbar_spacing()
            return
        reused_count = 0
        created_count = 0
        removed_count = 0
        replaced_count = 0

        for override_key in list(self._global_override_controls):
            if override_key not in active_by_key:
                if self._remove_override_widget(override_key):
                    removed_count += 1

        for control in toolbar_snapshot.active_controls:
            signature = self._override_control_signature(control)
            existing_control = self._global_override_controls.get(control.override_key)
            existing_signature = self._global_override_control_signatures.get(
                control.override_key
            )
            if existing_control is not None and existing_signature == signature:
                label_widget, widget = existing_control
                self._normalize_override_control(
                    active_by_key[control.override_key],
                    label_widget,
                    widget,
                )
                self._insert_override_widget(
                    override_key=control.override_key,
                    label_widget=label_widget,
                    widget=widget,
                )
                reused_count += 1
                continue
            if existing_control is not None:
                self._remove_override_widget(control.override_key)
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
        self._active_controls_signature = active_signature
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
            override_keys=tuple(sorted(self._global_overrides)),
            overrides=tuple(
                {
                    "override_key": key,
                    "value": _compact_log_value(value.get("value")),
                    "mode": value.get("mode"),
                }
                for key, value in sorted(self._global_overrides.items())
            ),
        )
        overrides_changed = self._service.apply_overrides_to_projection(
            overrides=self._global_overrides,
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
        return self._service.build_participation_snapshot(
            overrides=self._global_overrides,
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
        return self._service.build_serialization_scopes(
            overrides=self._global_overrides,
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
        participation = self._service.build_participation_snapshot(
            overrides=self._global_overrides,
            behavior_snapshot=behavior_snapshot,
            stack_order=self._current_projection_order(),
        )
        return set(participation.participant_fields())

    def project_seed_value_from_workflow(self, value: int) -> None:
        """Project the authoritative override seed without emitting user intent."""

        self.sync_state_from_workflow()
        control = self._global_override_controls.get("seed")
        if control is None:
            return
        _label, widget = control
        set_value = getattr(widget, "setValue", None)
        if not callable(set_value):
            return
        blocker = QSignalBlocker(widget)
        try:
            set_value(value)
        finally:
            del blocker

    def dispose(self) -> None:
        """Tear down toolbar widgets and clear in-memory override state."""

        try:
            self._clear_all_override_widgets()
        finally:
            self._global_overrides.clear()
            self._global_override_selections.clear()
            self._toolbar_snapshot = None

    def _on_override_menu_toggled(self, action: Any) -> None:
        """Handle checked and unchecked actions from the overrides drop-down menu."""

        workflow = self.mainwindow.get_active_workflow()
        behavior_snapshot = self._current_behavior_snapshot()
        if workflow is None or behavior_snapshot is None:
            return
        data = action.data() or {}
        override_key = data.get("override_key")
        if not isinstance(override_key, str):
            return

        workflow_overrides = self._service.normalize_workflow_overrides(
            getattr(workflow, "global_overrides", None)
        )
        workflow_selections = self._service.normalize_workflow_selections(
            getattr(workflow, "global_override_selections", None)
        )
        changed = False
        if bool(action.isChecked()):
            workflow_selections[override_key] = True
            changed = self._service.pin_override(
                overrides=workflow_overrides,
                behavior_snapshot=behavior_snapshot,
                stack_order=self._current_projection_order(),
                override_key=override_key,
            )
        else:
            workflow_selections[override_key] = False
            changed = self._service.unpin_override(workflow_overrides, override_key)

        if not changed and getattr(workflow, "global_override_selections", {}) == dict(
            workflow_selections
        ):
            return
        workflow.global_overrides = dict(workflow_overrides)
        workflow.global_override_selections = dict(workflow_selections)
        self.sync_state_from_workflow()
        self._refresh_toolbar_after_toggle()
        self._request_session_autosave()

    def _refresh_toolbar_after_toggle(self) -> None:
        """Rebuild local toolbar state after one menu toggle without repinning defaults."""

        self.rebuild_override_menu()
        self.rebuild_active_override_controls()
        self.apply_global_overrides()

    def _sync_overrides_to_workflow(self) -> None:
        """Persist current manager override state to the active workflow."""

        workflow = self.mainwindow.get_active_workflow()
        if workflow is not None:
            log_debug(
                _LOGGER,
                "syncing overrides to workflow",
                workflow_override_keys_before=tuple(
                    sorted(
                        str(key) for key in getattr(workflow, "global_overrides", {})
                    )
                ),
                manager_overrides=tuple(
                    {
                        "override_key": key,
                        "value": _compact_log_value(value.get("value")),
                        "mode": value.get("mode"),
                    }
                    for key, value in sorted(self._global_overrides.items())
                ),
            )
            workflow.global_overrides = dict(self._global_overrides)
            workflow.global_override_selections = dict(self._global_override_selections)

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
            override_keys=tuple(sorted(self._global_overrides)),
        )
        if workflow is None or behavior_snapshot is None:
            self._toolbar_snapshot = OverrideToolbarSnapshot([], [], ())
            return self._toolbar_snapshot
        self._toolbar_snapshot = self._service.build_toolbar_snapshot(
            behavior_snapshot=behavior_snapshot,
            stack_order=self._current_projection_order(),
            overrides=self._global_overrides,
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

        if override_key in self._global_override_selections:
            return self._global_override_selections[override_key]
        toolbar_snapshot = self._toolbar_snapshot
        if toolbar_snapshot is None:
            return override_key in self._global_overrides
        return override_key in toolbar_snapshot.active_override_keys

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

    def _remove_override_widget(self, override_key: str) -> bool:
        """Remove one toolbar label/widget pair when present."""

        if override_key not in self._global_override_controls:
            return False
        label_widget, widget = self._global_override_controls.pop(override_key)
        self._global_override_control_signatures.pop(override_key, None)
        self._active_controls_signature = None
        self.mainwindow.menu_bar_layout.removeWidget(label_widget)
        self._hide_widget(label_widget)
        label_widget.deleteLater()
        self.mainwindow.menu_bar_layout.removeWidget(widget)
        self._hide_widget(widget)
        widget.deleteLater()
        return True

    def detach_override_widgets(self) -> None:
        """Detach cached toolbar controls from the shared menu bar without disposal."""

        layout = self.mainwindow.menu_bar_layout
        for label_widget, widget in self._global_override_controls.values():
            if layout.indexOf(label_widget) >= 0:
                layout.removeWidget(label_widget)
            self._hide_widget(label_widget)
            if layout.indexOf(widget) >= 0:
                layout.removeWidget(widget)
            self._hide_widget(widget)

    def clear_toolbar_override_controls(self) -> None:
        """Detach all workflow override controls from the shared toolbar."""

        self._clear_all_override_widgets()

    def _clear_all_override_widgets(self) -> None:
        """Remove all active toolbar controls from the menu bar."""

        for override_key in list(self._global_override_controls.keys()):
            self._remove_override_widget(override_key)
        self._global_override_controls.clear()
        self._global_override_control_signatures.clear()
        self._active_controls_signature = None

    def _insert_override_widget(
        self,
        *,
        override_key: str,
        label_widget: Any,
        widget: Any,
    ) -> None:
        """Insert one toolbar label/widget pair using snapshot-defined active order."""

        layout = self.mainwindow.menu_bar_layout
        for existing_widget in (label_widget, widget):
            if layout.indexOf(existing_widget) >= 0:
                layout.removeWidget(existing_widget)

        active_keys = (
            list(self._toolbar_snapshot.active_override_keys)
            if self._toolbar_snapshot
            else []
        )
        base_index = self._override_toolbar_insert_base_index(layout)
        preceding_keys = (
            active_keys[: active_keys.index(override_key)]
            if override_key in active_keys
            else []
        )
        insert_index = base_index
        for existing_key in preceding_keys:
            existing_control = self._global_override_controls.get(existing_key)
            if existing_control is None:
                continue
            _existing_label, existing_widget = existing_control
            insert_index = max(insert_index, layout.indexOf(existing_widget) + 1)

        log_debug(
            _LOGGER,
            "insert override widget",
            override_key=override_key,
            base_index=base_index,
            insert_index=insert_index,
            active_keys=tuple(active_keys),
            preceding_keys=tuple(preceding_keys),
            label_widget_type=type(label_widget).__name__,
            widget_type=type(widget).__name__,
        )
        layout.insertWidget(insert_index, label_widget)
        layout.insertWidget(insert_index + 1, widget)
        self._show_widget(label_widget)
        self._show_widget(widget)

    def _override_toolbar_insert_base_index(self, layout: Any) -> int:
        """Return the first layout index available for active override controls."""

        anchor_widget = None
        if self.override_dropdown_btn is not None:
            property_getter = getattr(self.override_dropdown_btn, "property", None)
            if callable(property_getter):
                anchor_widget = property_getter("layoutAnchorWidget")

        for candidate in (anchor_widget, self.override_dropdown_btn):
            if candidate is None:
                continue
            index = int(layout.indexOf(candidate))
            if index >= 0:
                return index + 1
        return 0

    @staticmethod
    def _hide_widget(widget: Any) -> None:
        """Hide a detached toolbar widget when the Qt object supports it."""

        hide = getattr(widget, "hide", None)
        if callable(hide):
            hide()

    @staticmethod
    def _show_widget(widget: Any) -> None:
        """Show a mounted toolbar widget when the Qt object supports it."""

        show = getattr(widget, "show", None)
        if callable(show):
            show()

    def _active_override_controls_attached(
        self,
        active_by_key: dict[str, PinnedOverrideControl],
    ) -> bool:
        """Return whether all active cached controls are mounted in the menu bar."""

        layout = self.mainwindow.menu_bar_layout
        for override_key in active_by_key:
            existing_control = self._global_override_controls.get(override_key)
            if existing_control is None:
                return False
            label_widget, widget = existing_control
            if layout.indexOf(label_widget) < 0 or layout.indexOf(widget) < 0:
                return False
        return True

    def _normalize_existing_override_controls(
        self,
        active_by_key: dict[str, PinnedOverrideControl],
    ) -> None:
        """Reapply toolbar sizing to cached controls before reuse shortcuts return."""

        for override_key, control in active_by_key.items():
            existing_control = self._global_override_controls.get(override_key)
            if existing_control is None:
                continue
            label_widget, widget = existing_control
            self._normalize_override_control(control, label_widget, widget)

    def _normalize_override_control(
        self,
        control: PinnedOverrideControl,
        label_widget: Any,
        widget: Any,
    ) -> None:
        """Apply compact toolbar sizing to one active override label/control pair."""

        self._apply_toolbar_label_size(label_widget)
        self._apply_toolbar_widget_size(control.spec, widget)
        self._reconcile_model_override_picker(control, widget)

    def _reconcile_model_override_picker(
        self,
        control: PinnedOverrideControl,
        widget: object,
    ) -> None:
        """Refresh a model-backed override picker without replacing its widget."""

        spec = control.spec
        reconcile_choice_source = getattr(widget, "reconcile_choice_source", None)
        if not callable(reconcile_choice_source):
            return
        if (
            model_kind_for_field(
                class_type=spec.class_type,
                input_key=spec.field_key,
            )
            is None
        ):
            return
        snapshot_controller = self._model_choice_snapshot_controller
        if snapshot_controller is None:
            return
        from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
            PanelModelChoiceSnapshotRequest,
        )

        snapshot = snapshot_controller.snapshot_for_field(
            PanelModelChoiceSnapshotRequest(
                field_behavior=spec.field_behavior,
                node_name=spec.node_name,
                key=spec.field_key,
                value=control.value,
                node_type=spec.class_type,
                field_type=spec.field_type,
                field_info=spec.field_info,
                node_definition_gateway=self._node_definition_gateway,
                cube_alias=spec.cube_alias,
                thumbnail_repository_available=(
                    self._thumbnail_asset_repository is not None
                ),
            )
        )
        if snapshot.choice_source is not None:
            reconcile_choice_source(
                snapshot.choice_source,
                str(control.value or ""),
            )

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

        log_debug(
            _LOGGER,
            "create override widget started",
            override_key=control.override_key,
            value=_compact_log_value(control.value),
            representative_cube=control.spec.cube_alias,
            representative_node=control.spec.node_name,
            representative_class=control.spec.class_type,
            representative_field=control.spec.field_key,
            spec_value=_compact_log_value(control.spec.value),
            spec_raw_value=_compact_log_value(control.spec.raw_value),
            spec_value_source=control.spec.value_source.value,
        )
        widget_spec = self._toolbar_field_spec(control.spec, control.value)

        def build_override_surface() -> object | None:
            """Invoke the raw factory inside the shared typed outcome boundary."""

            return cast(
                object | None,
                build_widget_for_field_spec(
                    parent=self.mainwindow.menu_bar,
                    field_spec=widget_spec,
                    prompt_autocomplete_gateway=self._prompt_autocomplete_gateway,
                    prompt_wildcard_catalog_gateway=(
                        self._prompt_wildcard_catalog_gateway
                    ),
                    danbooru_url_import_service=self._danbooru_url_import_service,
                    danbooru_wiki_service=self._danbooru_wiki_service,
                    danbooru_image_preview_service=(
                        self._danbooru_image_preview_service
                    ),
                    danbooru_recent_posts_service=(self._danbooru_recent_posts_service),
                    prompt_lora_catalog_service=self._prompt_lora_catalog_service,
                    prompt_spellcheck_service=getattr(
                        self.mainwindow,
                        "prompt_spellcheck_service",
                        None,
                    ),
                    model_choice_snapshot_controller=(
                        self._model_choice_snapshot_controller
                    ),
                    thumbnail_asset_repository=self._thumbnail_asset_repository,
                    model_metadata_action_handler=self._model_metadata_action_handler,
                    node_definition_gateway=self._node_definition_gateway,
                ),
            )

        outcome = resolve_editor_field_build(
            field_spec=widget_spec,
            build=build_override_surface,
            layout_handled_sentinel=LAYOUT_HANDLED,
        )
        if outcome.kind is EditorFieldBuildKind.ERROR:
            error = outcome.error
            if error is None:
                return False
            log_warning_exception(
                _LOGGER,
                "Failed to build pinned override control",
                error=error,
                override_key=control.override_key,
                class_type=control.spec.class_type,
                field_key=control.spec.field_key,
            )
            return False
        if not outcome.rendered:
            log_warning(
                _LOGGER,
                "Skipped unavailable pinned override control",
                override_key=control.override_key,
                class_type=control.spec.class_type,
                field_key=control.spec.field_key,
                outcome=outcome.kind.value,
                reason=outcome.reason,
            )
            return False

        result = outcome.surface
        if result is None:
            return False
        widget = result[0] if isinstance(result, tuple) else result
        label_widget = CaptionLabel(
            beautify_label(control.label),
            self.mainwindow.menu_bar,
        )
        label_widget.setContentsMargins(4, 0, 4, 0)
        self._apply_toolbar_label_size(label_widget)
        self._apply_toolbar_widget_size(control.spec, widget)
        identify_override_surface(
            override_key=control.override_key,
            label_widget=label_widget,
            control_widget=widget,
        )
        from substitute.presentation.widgets.tooltips import (
            bind_fluent_tooltip,
            tooltip_from_field_meta,
        )

        bind_fluent_tooltip(
            label_widget,
            tooltip_from_field_meta(widget_spec.meta_info),
            label_widget,
            cast(QWidget, widget),
            show_delay_ms=600,
        )

        self._insert_override_widget(
            override_key=control.override_key,
            label_widget=label_widget,
            widget=widget,
        )
        self._global_override_controls[control.override_key] = (label_widget, widget)
        self._global_override_control_signatures[control.override_key] = (
            self._override_control_signature(control)
        )

        self._restore_override_seed_mode(control.override_key, widget)
        self._connect_override_seed_mode_signal(control.override_key, widget)
        bind_override_control(
            widget,
            partial(self._commit_override_value, control.override_key),
        )
        log_debug(
            _LOGGER,
            "create override widget completed",
            override_key=control.override_key,
            widget_type=type(widget).__name__,
            label_type=type(label_widget).__name__,
            widget_metadata=_compact_log_value(
                widget.property("input_metadata")
                if hasattr(widget, "property")
                else None
            ),
        )
        return True

    def _override_control_signature(
        self,
        control: PinnedOverrideControl,
    ) -> tuple[object, ...]:
        """Return the render contract used to decide toolbar control reuse."""

        spec = control.spec
        behavior = spec.field_behavior
        model_options_are_dynamic = (
            model_kind_for_field(
                class_type=spec.class_type,
                input_key=spec.field_key,
            )
            is not None
        )
        return (
            control.override_key,
            control.label,
            repr(control.value),
            spec.class_type,
            spec.field_key,
            spec.field_type,
            repr(sorted(spec.constraints.items())),
            "dynamic_model_options"
            if model_options_are_dynamic
            else repr(spec.field_info),
            ()
            if model_options_are_dynamic
            else self._choice_inventory_signature(control),
            behavior.presentation.value,
            behavior.control_name,
            repr(sorted(behavior.style.items())),
        )

    def _choice_inventory_signature(
        self,
        control: PinnedOverrideControl,
    ) -> tuple[str, ...]:
        """Return choice options that affect rendering and control reuse."""

        spec = control.spec
        if not is_choice_field_type(spec.field_type):
            return ()
        return resolve_choice_options_for_field(
            key=spec.field_key,
            node_type=spec.class_type,
            node_definition_gateway=self._node_definition_gateway,
            field_info=spec.field_info,
            value=control.value,
        )

    def _commit_override_value(
        self,
        override_key: str,
        value: object,
    ) -> None:
        """Persist one committed toolbar value and request session autosave."""
        workflow = self.mainwindow.get_active_workflow()
        if workflow is None:
            return
        workflow_overrides = self._service.normalize_workflow_overrides(
            getattr(workflow, "global_overrides", None)
        )
        log_debug(
            _LOGGER,
            "sync override from toolbar buffer",
            override_key=override_key,
            value=_compact_log_value(value),
            previous_value=_compact_log_value(
                workflow_overrides.get(override_key, {}).get("value")
            ),
        )
        self._service.set_override_value(workflow_overrides, override_key, value)
        workflow.global_overrides = dict(workflow_overrides)
        self.sync_state_from_workflow()
        self.apply_global_overrides()
        self._request_session_autosave()

    def _restore_override_seed_mode(self, override_key: str, widget: Any) -> None:
        """Restore seed mode for one override toolbar seed widget."""

        if not self._is_seed_override_widget(override_key, widget):
            return
        set_mode = getattr(widget, "setMode", None)
        if not callable(set_mode):
            return
        set_mode(self._override_seed_mode(override_key).value)

    def _connect_override_seed_mode_signal(
        self,
        override_key: str,
        widget: Any,
    ) -> None:
        """Persist seed mode changes from one override toolbar seed widget."""

        if not self._is_seed_override_widget(override_key, widget):
            return
        mode_changed = getattr(widget, "modeChanged", None)
        if mode_changed is None or not hasattr(mode_changed, "connect"):
            return
        mode_changed.connect(
            lambda mode, key=override_key: self._sync_override_seed_mode(key, mode)
        )

    def _override_seed_mode(self, override_key: str) -> SeedMode:
        """Return workflow-owned seed mode for one override key."""

        workflow = self.mainwindow.get_active_workflow()
        canonical_key = self._service.canonicalize_override_key(override_key)
        states = getattr(workflow, "override_control_states", None)
        if not isinstance(states, dict):
            return SeedMode.RANDOM
        state = states.get(canonical_key)
        return state.mode if isinstance(state, SeedControlState) else SeedMode.RANDOM

    def _sync_override_seed_mode(self, override_key: str, mode: object) -> None:
        """Persist seed random/fixed mode without changing override participation mode."""

        workflow = self.mainwindow.get_active_workflow()
        if workflow is None:
            return
        canonical_key = self._service.canonicalize_override_key(override_key)
        next_state = SeedControlState(seed_mode_from_value(mode))
        states = getattr(workflow, "override_control_states", None)
        if not isinstance(states, dict):
            states = {}
            setattr(workflow, "override_control_states", states)
        previous = states.get(canonical_key)
        if isinstance(previous, SeedControlState) and previous.mode == next_state.mode:
            return
        states[canonical_key] = next_state
        self._request_session_autosave()
        log_debug(
            _LOGGER,
            "persisted override seed mode",
            override_key=canonical_key,
            seed_mode=next_state.mode.value,
        )

    def _is_seed_override_widget(self, override_key: str, widget: Any) -> bool:
        """Return whether one toolbar widget carries seed random/fixed mode."""

        canonical_key = self._service.canonicalize_override_key(override_key)
        return (
            canonical_key == "seed"
            and widget.__class__.__name__ == "SeedBox"
            and hasattr(widget, "modeChanged")
        )

    @staticmethod
    def _toolbar_field_spec(spec: ResolvedFieldSpec, value: Any) -> ResolvedFieldSpec:
        """Return the toolbar render spec derived from one representative field spec."""

        toolbar_meta = dict(spec.meta_info)
        toolbar_meta["node_data"] = None
        return ResolvedFieldSpec(
            cube_alias=spec.cube_alias,
            node_name=spec.node_name,
            class_type=spec.class_type,
            field_key=spec.field_key,
            field_type=spec.field_type,
            constraints=dict(spec.constraints),
            meta_info=toolbar_meta,
            field_info=list(spec.field_info) if spec.field_info is not None else None,
            value=value,
            field_behavior=spec.field_behavior,
            raw_value=spec.raw_value,
            value_source=spec.value_source,
        )

    def _request_session_autosave(self) -> None:
        """Request persistence after one user-owned override mutation."""

        request_autosave = getattr(self.mainwindow, "request_session_autosave", None)
        if callable(request_autosave):
            request_autosave()

    @staticmethod
    def _apply_toolbar_label_size(label_widget: Any) -> None:
        """Keep override toolbar labels from absorbing horizontal toolbar slack."""

        if hasattr(label_widget, "setSizePolicy"):
            label_widget.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Preferred,
            )

    @staticmethod
    def _apply_toolbar_widget_size(spec: ResolvedFieldSpec, widget: Any) -> None:
        """Keep override controls compact while allowing width-pressure shrinkage."""

        if spec.field_behavior.presentation is FieldPresentation.SEED_BOX:
            restore_size_contract = getattr(widget, "restore_size_contract", None)
            if callable(restore_size_contract):
                restore_size_contract()
            return
        if hasattr(widget, "setSizePolicy"):
            widget.setSizePolicy(
                QSizePolicy.Policy.Maximum,
                QSizePolicy.Policy.Fixed,
            )
        if spec.field_type in {"INT", "FLOAT"}:
            if hasattr(widget, "setFixedHeight"):
                widget.setFixedHeight(_TOOLBAR_CONTROL_HEIGHT)
            return
        if hasattr(widget, "setMaximumWidth"):
            widget.setMaximumWidth(_TOOLBAR_MAX_WIDGET_WIDTH)

    def _fallback_hidden_field_keys(
        self,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> set[object]:
        """Return conservative hidden-field keys when unified recompute is unavailable."""

        if behavior_snapshot is None:
            return set()
        return self._override_hidden_field_keys(behavior_snapshot)


__all__ = ["GlobalOverridesManager"]
