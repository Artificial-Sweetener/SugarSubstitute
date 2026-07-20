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

"""Own panel projection lifecycle cleanup and runtime issue integration."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol, TypeVar, cast

from substitute.application.node_behavior import LiveNodeDefinitionError
from substitute.application.workflows import (
    CubeRuntimeIssueSource,
    update_node_link_references_on_rename,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_timing,
    log_warning,
)

from .factories.meta_factories import (
    update_prompt_link_references_on_rename,
    update_sampler_link_references_on_rename,
    update_scheduler_link_references_on_rename,
)
from .projection_preparation import (
    BehaviorRefreshReason,
    without_cube_aliases,
    without_stack_aliases,
)
from .projection_session import ActiveProjectionSession

_LOGGER = get_logger("presentation.editor.panel.projection_lifecycle")
_T = TypeVar("_T")


class ProjectionBuildRegistryPort(Protocol):
    """Describe build-registry cleanup used by lifecycle transitions."""

    def forget(self, alias: str) -> object | None:
        """Forget one alias-scoped build record."""

    def clear(self) -> None:
        """Clear all build records."""


class ProjectionCompletionPort(Protocol):
    """Describe pending insert cancellation used during layout clearing."""

    def cancel_all_pending_inserts(self, *, reason: str) -> None:
        """Cancel pending insert completions for the supplied reason."""


class VisibleProjectionCommitPort(Protocol):
    """Describe visible commit cleanup used during layout clearing."""

    def discard_pending_visible_projection_commit(self, *, reason: str) -> None:
        """Discard any deferred visible projection commit."""


class RenderReconcilerPort(Protocol):
    """Describe layout reconciliation used by stack reorder."""

    def clear_layout(self) -> None:
        """Detach managed root-layout widgets."""

    def append_cube_widget_to_layout(self, cube_widget: object) -> None:
        """Append one cube widget to the root cube layout."""


class _LayoutItemPort(Protocol):
    """Describe layout-item cleanup access used by lifecycle clearing."""

    def widget(self) -> object | None:
        """Return the contained widget, when present."""

    def layout(self) -> object | None:
        """Return the nested layout, when present."""


class _LayoutPort(Protocol):
    """Describe root layout operations used by lifecycle clearing."""

    def count(self) -> int:
        """Return the number of root layout items."""

    def takeAt(self, index: int) -> _LayoutItemPort:
        """Remove one root layout item."""


class ProjectionLifecyclePanelPort(Protocol):
    """Describe panel state and operations owned by projection lifecycle."""

    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None
    _layout: _LayoutPort
    cube_widgets: dict[str, object]
    cube_sections: dict[str, object]
    cube_headers: dict[str, object]
    card_wrappers: dict[object, object]
    input_widgets_by_field_key: dict[object, object]
    row_widgets: dict[object, object]
    col_widgets: dict[object, object]
    meta_registry: object

    def sanitize_prompt_link_state(self) -> None:
        """Sanitize prompt-link state after structural cube changes."""

    def _refresh_sampler_scheduler_link_state(self) -> None:
        """Refresh sampler and scheduler link state."""

    def _refresh_link_widgets(self) -> None:
        """Refresh visible link widgets."""

    def refresh_node_behavior_state(
        self,
        *,
        reason: BehaviorRefreshReason,
        use_cached_snapshot: bool = False,
    ) -> None:
        """Refresh behavior-derived visibility state."""


class RuntimeIssueIntegrationPanelPort(Protocol):
    """Describe panel hooks used for projection-time runtime issue handoff."""

    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None

    def hydrate_node_definitions_for_projection(self, *, reason: str) -> None:
        """Hydrate node definitions required by projection."""


@dataclass(frozen=True, slots=True)
class EditorProjectionLifecyclePorts:
    """Group collaborators used by projection lifecycle transitions."""

    panel: ProjectionLifecyclePanelPort
    build_registry: ProjectionBuildRegistryPort
    projection_completions: ProjectionCompletionPort
    visible_commits: VisibleProjectionCommitPort
    render_reconciler: RenderReconcilerPort
    active_projection_session: Callable[[], ActiveProjectionSession | None]
    cancel_active_projection_session: Callable[[ActiveProjectionSession, str], None]
    invalidate_projection: Callable[[str], None]


class EditorProjectionLifecyclePipeline:
    """Own remove, rename, reorder, and clear projection lifecycle orchestration."""

    def __init__(self, ports: EditorProjectionLifecyclePorts) -> None:
        """Store explicit lifecycle collaborators without owning the coordinator."""

        self._ports = ports

    def remove_cube(self, cube_alias: str) -> None:
        """Remove one cube from projection state and refresh derived visibility."""

        panel = self._ports.panel
        clear_issue = getattr(panel, "clear_cube_runtime_issues", None)
        if callable(clear_issue):
            clear_issue(cube_alias)
        self.discard_cube_widget(cube_alias, reason="cube_removed")
        self.refresh_visibility(
            message=app_text("Failed to refresh editor visibility after cube removal"),
            reason="cube_removed",
        )
        self._ports.invalidate_projection("cube_removed")

    def rename_cube(self, old_alias: str, new_alias: str) -> None:
        """Rename one cube and refresh projection-derived link state."""

        panel = self._ports.panel
        rename_alias = self._cube_registry_rename()
        if rename_alias is not None:
            rename_alias(old_alias, new_alias)
        rename_node_link_alias = getattr(
            getattr(panel, "meta_registry", None),
            "rename_node_link_alias",
            None,
        )
        if callable(rename_node_link_alias):
            rename_node_link_alias(old_alias, new_alias)

        if panel._cube_states and panel._stack_order:
            all_buffers = {
                alias: cast(
                    dict[str, Any], getattr(panel._cube_states[alias], "buffer")
                )
                for alias in panel._stack_order
                if alias in panel._cube_states
            }
            update_prompt_link_references_on_rename(
                all_buffers,
                old_alias,
                new_alias,
            )
            update_node_link_references_on_rename(
                all_buffers,
                old_alias,
                new_alias,
            )
            update_sampler_link_references_on_rename(
                all_buffers,
                old_alias,
                new_alias,
            )
            update_scheduler_link_references_on_rename(
                all_buffers,
                old_alias,
                new_alias,
            )
            panel.sanitize_prompt_link_state()
            panel._refresh_sampler_scheduler_link_state()

        panel._refresh_link_widgets()
        self.refresh_visibility(
            message=app_text("Failed to refresh editor visibility after cube rename"),
            reason="cube_renamed",
        )
        self._ports.invalidate_projection("cube_renamed")

    def reorder_cube_widgets(self) -> None:
        """Reattach cube widgets in stack order and refresh link widgets once."""

        panel = self._ports.panel
        if not panel._stack_order:
            return
        refresh_started_at = perf_counter()

        panel.sanitize_prompt_link_state()
        panel._refresh_sampler_scheduler_link_state()
        self._ports.render_reconciler.clear_layout()

        for alias in panel._stack_order:
            widget = panel.cube_widgets.get(alias)
            if widget is None:
                continue
            self._ports.render_reconciler.append_cube_widget_to_layout(widget)

        panel._refresh_link_widgets()
        self.refresh_visibility(
            message=app_text("Failed to refresh editor visibility after cube reorder"),
            reason="stack_reordered",
        )
        log_timing(
            _LOGGER,
            "Reordered editor cube widgets",
            started_at=refresh_started_at,
            cube_section_count=len(panel._stack_order),
            existing_widget_count=len(panel.cube_widgets),
            level="debug",
        )

    def clear_layout(self) -> None:
        """Dispose rendered projection widgets and clear projection lifecycle state."""

        panel = self._ports.panel
        clear_model_progress = getattr(panel, "clear_model_field_load_progress", None)
        if callable(clear_model_progress):
            clear_model_progress()
        log_debug(
            _LOGGER,
            "Clearing editor panel layout",
            card_wrapper_count=len(panel.card_wrappers),
            cube_position_count=len(getattr(panel, "cube_positions", {})),
            cube_visibility_button_count=len(
                getattr(panel, "_cube_visibility_btns", {}),
            ),
            cube_visibility_menu_count=len(
                getattr(panel, "_cube_visibility_menus", {}),
            ),
            cube_widget_count=len(panel.cube_widgets),
            cube_header_count=len(panel.cube_headers),
            node_link_widget_count=len(getattr(panel, "node_link_widgets", {})),
        )

        active_session = self._ports.active_projection_session()
        if active_session is not None:
            self._ports.cancel_active_projection_session(
                active_session,
                "layout_cleared",
            )
        self._ports.visible_commits.discard_pending_visible_projection_commit(
            reason="layout_cleared",
        )
        self._ports.projection_completions.cancel_all_pending_inserts(
            reason="layout_cleared",
        )
        self._ports.build_registry.clear()

        panel.cube_widgets.clear()
        panel.cube_sections.clear()
        self._clear_link_registries()
        self._clear_child_widget_registries()
        self._clear_root_layout()
        getattr(panel, "cube_positions", {}).clear()
        self._ports.invalidate_projection("layout_cleared")
        log_debug(
            _LOGGER,
            "Cleared editor panel layout",
            card_wrapper_count=len(panel.card_wrappers),
            cube_position_count=len(getattr(panel, "cube_positions", {})),
            cube_visibility_button_count=len(
                getattr(panel, "_cube_visibility_btns", {}),
            ),
            cube_visibility_menu_count=len(
                getattr(panel, "_cube_visibility_menus", {}),
            ),
            cube_widget_count=len(panel.cube_widgets),
            cube_header_count=len(panel.cube_headers),
            node_link_widget_count=len(getattr(panel, "node_link_widgets", {})),
        )

    def remove_closed_aliases(self, current_aliases: set[str]) -> None:
        """Dispose widgets and runtime issues for aliases no longer present."""

        panel = self._ports.panel
        for alias in list(panel.cube_widgets.keys()):
            if alias in current_aliases:
                continue
            clear_issue = getattr(panel, "clear_cube_runtime_issues", None)
            if callable(clear_issue):
                clear_issue(alias)
            self.discard_cube_widget(alias, reason="closed_alias")

    def discard_cube_widget(self, cube_alias: str, *, reason: str) -> None:
        """Remove one rendered cube widget and its projection ownership record."""

        panel = self._ports.panel
        widget = panel.cube_widgets.pop(cube_alias, None)
        panel.cube_sections.pop(cube_alias, None)
        panel.cube_headers.pop(cube_alias, None)
        self._ports.build_registry.forget(cube_alias)
        self.clear_alias_scoped_panel_registries(cube_alias)
        if widget is None:
            return
        hide = getattr(widget, "hide", None)
        if callable(hide):
            hide()
        remove_widget = getattr(panel, "_remove_cube_widget_from_layout", None)
        if callable(remove_widget):
            remove_widget(widget)
        else:
            set_parent = getattr(widget, "setParent", None)
            if callable(set_parent):
                set_parent(None)
        log_info(
            _LOGGER,
            "Discarded editor cube section widget",
            cube_alias=cube_alias,
            reason=reason,
        )

    def clear_alias_scoped_panel_registries(self, cube_alias: str) -> None:
        """Clear editor registries whose entries belong to one cube alias."""

        panel = self._ports.panel
        field_registry = getattr(panel, "_field_registry", None)
        remove_registered_cube = getattr(field_registry, "remove_cube", None)
        if callable(remove_registered_cube):
            remove_registered_cube(cube_alias)
        else:
            _remove_alias_keyed_entries(
                getattr(panel, "input_widgets_by_field_key", None),
                cube_alias,
            )
        _remove_alias_keyed_entries(getattr(panel, "row_widgets", None), cube_alias)
        _remove_alias_keyed_entries(getattr(panel, "col_widgets", None), cube_alias)
        _remove_alias_keyed_entries(
            getattr(panel, "_last_card_decisions", None),
            cube_alias,
        )
        hidden_keys = getattr(panel, "_last_hidden_field_keys", None)
        if isinstance(hidden_keys, set):
            setattr(
                panel,
                "_last_hidden_field_keys",
                {key for key in hidden_keys if not _alias_key_matches(key, cube_alias)},
            )
        remove_node_link_cube = getattr(
            getattr(panel, "meta_registry", None),
            "remove_node_link_cube",
            None,
        )
        if callable(remove_node_link_cube):
            remove_node_link_cube(cube_alias)
        card_wrappers = getattr(panel, "card_wrappers", None)
        if isinstance(card_wrappers, dict):
            for key in [
                key for key in card_wrappers if _alias_key_matches(key, cube_alias)
            ]:
                card_wrappers.pop(key, None)

    def refresh_visibility(
        self,
        *,
        message: str,
        reason: BehaviorRefreshReason,
        use_cached_snapshot: bool = False,
    ) -> None:
        """Run an immediate behavior refresh and log failures with shared context."""

        try:
            self._ports.panel.refresh_node_behavior_state(
                reason=reason,
                use_cached_snapshot=use_cached_snapshot,
            )
        except (RuntimeError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                message,
                reason=reason,
                error_type=type(error).__name__,
            )

    def _cube_registry_rename(self) -> Callable[[str, str], None] | None:
        """Return the cube-registry rename hook supplied by the panel."""

        panel = self._ports.panel
        registry_controller = getattr(panel, "_cube_registry_controller", None)
        registry = registry_controller() if callable(registry_controller) else None
        if registry is None:
            registry = getattr(panel, "_cube_registry", None)
        rename_alias = getattr(registry, "rename_cube_alias", None)
        return rename_alias if callable(rename_alias) else None

    def _clear_link_registries(self) -> None:
        """Clear link widget registries while preserving meta-registry cleanup hooks."""

        panel = self._ports.panel
        meta_registry = getattr(panel, "meta_registry", None)
        cleanup_dead_node_link_widgets = getattr(
            meta_registry,
            "cleanup_dead_node_link_widgets",
            None,
        )
        if callable(cleanup_dead_node_link_widgets):
            cleanup_dead_node_link_widgets()
        clear_node_link_title_surfaces = getattr(
            meta_registry,
            "clear_node_link_title_surfaces",
            None,
        )
        if callable(clear_node_link_title_surfaces):
            clear_node_link_title_surfaces()
        for attribute_name in (
            "node_link_widgets",
            "node_link_title_surfaces",
        ):
            mapping = getattr(panel, attribute_name, None)
            if isinstance(mapping, dict):
                mapping.clear()

    def _clear_child_widget_registries(self) -> None:
        """Clear cube-scoped child widget registries after layout disposal starts."""

        panel = self._ports.panel
        setattr(panel, "row_widgets", {})
        setattr(panel, "col_widgets", {})
        field_registry = getattr(panel, "_field_registry", None)
        clear_registered_fields = getattr(field_registry, "clear", None)
        if callable(clear_registered_fields):
            clear_registered_fields()
            setattr(
                panel,
                "input_widgets_by_field_key",
                getattr(field_registry, "widget_map", {}),
            )
        else:
            setattr(panel, "input_widgets_by_field_key", {})
        node_card_mode_controller = getattr(
            panel,
            "_node_card_mode_controller",
            None,
        )
        clear_card_mode_bindings = getattr(node_card_mode_controller, "clear", None)
        if callable(clear_card_mode_bindings):
            clear_card_mode_bindings()
        panel.card_wrappers.clear()
        getattr(panel, "_cube_visibility_btns", {}).clear()
        getattr(panel, "_cube_visibility_menus", {}).clear()
        panel.cube_headers.clear()

    def _clear_root_layout(self) -> None:
        """Dispose every root layout item using panel-owned recursive cleanup."""

        panel = self._ports.panel
        while panel._layout.count():
            item = panel._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                delete_later = getattr(widget, "deleteLater", None)
                if callable(delete_later):
                    delete_later()
                continue
            nested_layout = item.layout()
            if nested_layout is None:
                continue
            clear_nested_layout = getattr(panel, "_clear_layout_recursive", None)
            if callable(clear_nested_layout):
                clear_nested_layout(nested_layout)


class EditorProjectionRuntimeIssueIntegration:
    """Own projection-time runtime issue handoff to the runtime issue presenter."""

    def __init__(self, panel: RuntimeIssueIntegrationPanelPort) -> None:
        """Store panel hooks used during runtime issue integration."""

        self._panel = panel

    def begin_live_node_definition_report_projection(self) -> None:
        """Start a projection-scoped live metadata report dedupe window."""

        begin_reports = getattr(
            self._panel,
            "begin_live_node_definition_report_projection",
            None,
        )
        if callable(begin_reports):
            begin_reports()

    def hydrate_node_definitions_for_projection(
        self,
        *,
        reason: str,
        workflow_id: str,
    ) -> None:
        """Hydrate definitions and update projection runtime issue state."""

        panel = self._panel
        try:
            panel.hydrate_node_definitions_for_projection(reason=reason)
        except LiveNodeDefinitionError as error:
            if not self.register_recoverable_live_definition_error(
                error,
                reason=reason,
                workflow_id=workflow_id,
            ):
                raise
        else:
            clear_projection_issues = getattr(
                panel,
                "clear_projection_runtime_issues",
                None,
            )
            if callable(clear_projection_issues):
                clear_projection_issues()

    def register_recoverable_live_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
        workflow_id: str,
    ) -> bool:
        """Register a cube-attributed live metadata error or report fatal failure."""

        panel = self._panel
        register = getattr(
            panel,
            "register_projection_live_node_definition_error",
            None,
        )
        handled = (
            bool(
                register(
                    error,
                    reason=reason,
                    source=CubeRuntimeIssueSource.PROJECTION,
                )
            )
            if callable(register)
            else False
        )
        if handled:
            present_recoverable = getattr(
                panel,
                "present_recoverable_live_node_definition_error",
                None,
            )
            if callable(present_recoverable):
                present_recoverable(error, reason=reason)
            else:
                self._present_live_node_definition_error(error, reason=reason)
            log_warning(
                _LOGGER,
                "Recovered editor projection from cube-attributed live metadata error",
                workflow_id=workflow_id,
                reason=reason,
                missing_node_classes=",".join(
                    item.class_type for item in error.missing_definitions
                ),
            )
            return True
        self._present_live_node_definition_error(error, reason=reason)
        return False

    def cube_runtime_error_aliases(self) -> frozenset[str]:
        """Return current runtime error aliases from the panel when available."""

        error_aliases = getattr(
            self._panel,
            "cube_runtime_error_aliases",
            None,
        )
        return frozenset(error_aliases() if callable(error_aliases) else ())

    def is_errored_cube(self, cube_alias: str) -> bool:
        """Return whether a cube should render with the error section."""

        return cube_alias in self.cube_runtime_error_aliases()

    def run_projection_metadata_step(
        self,
        *,
        workflow_id: str,
        reason: str,
        action: Callable[[frozenset[str]], _T],
    ) -> _T:
        """Retry one metadata-dependent projection step after issue discovery."""

        errored_aliases = self.cube_runtime_error_aliases()
        while True:
            try:
                return action(errored_aliases)
            except LiveNodeDefinitionError as error:
                if not self.register_recoverable_live_definition_error(
                    error,
                    reason=reason,
                    workflow_id=workflow_id,
                ):
                    raise
                updated_aliases = self.cube_runtime_error_aliases()
                if updated_aliases == errored_aliases:
                    raise
                errored_aliases = updated_aliases

    def run_with_pruned_panel_state(
        self,
        errored_aliases: frozenset[str],
        action: Callable[[], _T],
    ) -> _T:
        """Run an editor operation while hiding errored cubes from panel state."""

        panel = self._panel
        full_cube_states = panel._cube_states
        full_stack_order = list(panel._stack_order) if panel._stack_order else None
        if errored_aliases and panel._cube_states is not None:
            panel._cube_states = dict(
                without_cube_aliases(panel._cube_states, errored_aliases) or {}
            )
            panel._stack_order = without_stack_aliases(
                panel._stack_order,
                errored_aliases,
            )
        try:
            return action()
        finally:
            panel._cube_states = full_cube_states
            panel._stack_order = full_stack_order

    def _present_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
    ) -> None:
        """Route a blocking live metadata report through the runtime presenter."""

        present = getattr(
            self._panel,
            "_present_live_node_definition_error",
            None,
        )
        if callable(present):
            present(error, reason=reason)


def _remove_alias_keyed_entries(mapping: object, cube_alias: str) -> None:
    """Remove entries whose tuple key is scoped to one cube alias."""

    if not isinstance(mapping, dict):
        return
    for key in [key for key in mapping if _alias_key_matches(key, cube_alias)]:
        mapping.pop(key, None)


def _alias_key_matches(key: object, cube_alias: str) -> bool:
    """Return whether one registry key belongs to the supplied cube alias."""

    return isinstance(key, tuple) and bool(key) and key[0] == cube_alias
