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

"""Build editor node-card widgets from prepared panel inputs."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import IconWidget
from shiboken6 import delete

try:
    from qfluentwidgets.common.font import setFont  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - test-stub fallback only

    def setFont(_widget: object, _font_size: int = 14, _weight: int = 50) -> None:
        """Provide a no-op font helper when qfluentwidgets is unavailable."""


from substitute.application.display_labels import beautify_label
from substitute.application.node_behavior import (
    CollapseMode,
    FieldBehavior,
    FieldPresentation,
    NodeDisplayDecision,
    ResolvedFieldSpec,
    ResolvedNodeBehavior,
    TitleControl,
)
from .node_card.accordion_motion import (
    AccordionChevronWidget,
    AccordionContentClip,
    AccordionMotionController,
    set_accordion_surface_attachment,
)
from substitute.presentation.editor.panel.menus.dimension_preset_models import (
    DimensionPresetMenuSource,
)
from .factories.meta_factories import build_enabled_switch
from .node_card.mode_controller import (
    NodeCardModeBinding,
    apply_title_row_interaction,
)
from .node_card.variant import resolve_node_card_variant
from substitute.presentation.editor.panel.menus.node_input_preset_menu_source import (
    NodeInputPresetSource,
)
from substitute.presentation.editor.panel.menus.node_title_preset_actions import (
    NodeInputPresetContext,
    bind_node_title_preset_actions,
)
from substitute.presentation.editor.panel.factories import widget_wiring
from substitute.presentation.editor.panel.factories.field_pipeline import (
    LAYOUT_HANDLED,
    build_widget_for_field_spec,
)
from substitute.presentation.editor.panel.field_state_controller import (
    EditorFieldBinding,
    EditorPanelFieldStateController,
)
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshotController,
)
from substitute.presentation.editor.panel.prompt_profile_policy import (
    PanelPromptFieldProfileDecision,
)
from substitute.presentation.editor.panel.projection_observability import (
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)
from substitute.presentation.editor.panel.service_bundle import EditorPanelServiceBundle
from substitute.presentation.editor.panel.widgets.field_row import (
    BuiltFieldRow,
    EDITOR_ROW_HORIZONTAL_MARGINS,
    EDITOR_ROW_ICON_SIZE,
    EDITOR_ROW_SPACING,
    FieldRowBuilder,
    bind_field_widget_card_relayout,
)
from substitute.presentation.editor.panel.widgets.node_card import (
    NODE_CARD_BODY_BOTTOM_PADDING,
    NODE_CARD_BODY_ROW_SPACING,
    NODE_CARD_BODY_TOP_PADDING,
    NODE_CARD_TITLE_HEIGHT,
    NODE_CARD_TITLE_ICON_SIZE,
    NODE_CARD_TITLE_ICON_SLOT_SIZE,
    _NODE_CARD_SURFACE_VERTICAL_PADDING,
    _NodeCardContentSurface,
    _NodeCardHeaderSurface,
    _NodeCardSurface,
    NodeCardWidget,
    reconcile_node_card_body_separators,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetSource,
)
from substitute.presentation.widgets.tooltips import (
    bind_fluent_tooltip,
    normalized_tooltip,
    tooltip_from_field_meta,
)
from substitute.presentation.editor.utils import sanitation
from substitute.presentation.editor.utils.create_vbox import create_vbox
from substitute.presentation.qt_label_text import literal_label_text
from substitute.presentation.resources.app_icon import AppIcon
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_warning,
)

_LOGGER = get_logger("presentation.editor.panel.node_card_builder")


@dataclass(frozen=True)
class NodePanelSnapshot:
    """Capture the panel state NodeCardBuilder needs for one build pass."""

    cube_id: str | None
    current_alias: str | None
    cube_states: Mapping[str, Any]
    stack_order: Sequence[str]

    def first_alias_for_class_type(self, node_type: str) -> str | None:
        """Return the first cube alias in stack order containing the requested node type."""

        for alias in self.stack_order:
            cube_state = self.cube_states.get(alias)
            buffer = getattr(cube_state, "buffer", {}) if cube_state is not None else {}
            for node_data in (buffer.get("nodes", {}) or {}).values():
                if (
                    isinstance(node_data, dict)
                    and node_data.get("class_type") == node_type
                ):
                    return alias
        return None


@dataclass(frozen=True)
class NodeCardPromptFieldInputs:
    """Carry prompt-context values prepared by Phase 13 owners for one field."""

    scheduled_lora_resolver: Callable[[str], object] | None = None
    prompt_field_profile: PanelPromptFieldProfileDecision | None = None


@dataclass(frozen=True, slots=True)
class _NodeCardBuildLogContext:
    """Carry prompt-safe node-card build diagnostic fields."""

    cube_alias: str
    node_name: str
    node_class: str
    field_spec_count: int


@dataclass(frozen=True, slots=True)
class _NodeCardFieldLogContext:
    """Carry prompt-safe node-card field diagnostic fields."""

    cube_alias: str
    node_name: str
    node_class: str
    field_key: str
    field_type: str
    presentation: str


def _log_node_card_build_timing(
    event: str,
    *,
    started_at: float,
    context: _NodeCardBuildLogContext,
    visible_group_count: int | None = None,
    has_rows: bool | None = None,
    has_title_controls: bool | None = None,
) -> float:
    """Log timing for one prompt-safe node-card build operation."""

    return log_panel_projection_timing(
        event,
        started_at=started_at,
        cube_alias=context.cube_alias,
        node_name=context.node_name,
        node_class=context.node_class,
        field_spec_count=context.field_spec_count,
        projection_mode="live",
        visible_group_count=visible_group_count,
        has_rows=has_rows,
        has_title_controls=has_title_controls,
    )


def _log_node_card_field_timing(
    event: str,
    *,
    started_at: float,
    context: _NodeCardFieldLogContext,
    result_type: str = "",
    widget_type: str = "",
) -> float:
    """Log timing for one prompt-safe node-card field operation."""

    return log_panel_projection_timing(
        event,
        started_at=started_at,
        cube_alias=context.cube_alias,
        node_name=context.node_name,
        node_class=context.node_class,
        field_key=context.field_key,
        field_type=context.field_type,
        presentation=context.presentation,
        projection_mode="live",
        result_type=result_type,
        widget_type=widget_type,
    )


def _switch_override_for_next_state(
    decision: NodeDisplayDecision,
    next_checked: bool,
) -> bool | None:
    """Return the explicit activation override represented by the next switch state."""

    if next_checked:
        return None if decision.policy_default_enabled else True
    return False


def _apply_node_activation_change(
    panel: Any,
    services: EditorPanelServiceBundle,
    cube_state: Any,
    node_name: str,
    display_decision: NodeDisplayDecision,
    checked: bool,
) -> None:
    """Persist one title-switch activation change through the panel service."""

    explicit_override = _switch_override_for_next_state(display_decision, checked)
    services.node_behavior_service.set_node_activation_override(
        cube_state,
        node_name,
        explicit_override,
    )
    panel.refresh_node_behavior_state(reason="node_activation_changed")


class NodeCardBodyComposer:
    """Own node-card body ordering, separators, and row visibility registration."""

    def __init__(self, *, panel: Any, field_rows: FieldRowBuilder) -> None:
        """Store the collaborators used to build rows and separator widgets."""

        self._panel = panel
        self._field_rows = field_rows

    def add_input_row(
        self,
        *,
        label: str,
        widget: QWidget,
        field_behavior: FieldBehavior,
        content_layout: QVBoxLayout,
    ) -> None:
        """Build and append one single-field row with body-owned separators."""

        self._append_row(
            content_layout,
            self._field_rows.build_input_row(
                label=label,
                widget=widget,
                field_behavior=field_behavior,
            ),
        )

    def add_n_column_row(
        self,
        *,
        fields: list[tuple[str, QWidget]],
        field_behaviors: Mapping[str, FieldBehavior],
        content_layout: QVBoxLayout,
        node_name: str = "",
    ) -> None:
        """Build and append one grouped row with body-owned separators."""

        self._append_row(
            content_layout,
            self._field_rows.build_n_column_row(
                fields=fields,
                field_behaviors=field_behaviors,
                node_name=node_name,
            ),
        )

    def _append_row(
        self,
        content_layout: QVBoxLayout,
        built_row: BuiltFieldRow,
    ) -> None:
        """Append a row and insert a separator only between body rows."""

        separator = self._create_separator(content_layout, built_row)
        content_layout.addWidget(built_row.row)
        self._register_row_widgets(built_row, separator)

    def _create_separator(
        self,
        content_layout: QVBoxLayout,
        built_row: BuiltFieldRow,
    ) -> QWidget | None:
        """Create the separator before a row when a previous body row exists."""

        if content_layout.count() == 0:
            return None
        parent = content_layout.parentWidget() or self._panel
        separator = self._field_rows.make_horizontal_divider(parent)
        if built_row.field_key is not None:
            separator.setProperty("divider_for_field", built_row.field_key)
        separator.setVisible(False)
        content_layout.addWidget(separator)
        return separator

    def reconcile_separator_visibility(self) -> None:
        """Show separators only between adjacent visible body rows."""

        row_widgets = getattr(self._panel, "row_widgets", {})
        if isinstance(row_widgets, Mapping):
            reconcile_node_card_body_separators(row_widgets)

    def _register_row_widgets(
        self,
        built_row: BuiltFieldRow,
        separator: QWidget | None,
    ) -> None:
        """Register row widgets with the panel for hidden-field controllers."""

        if built_row.field_key is None or not hasattr(self._panel, "row_widgets"):
            return
        self._panel.row_widgets[built_row.field_key] = (separator, built_row.row)


class NodeCardBuilder:
    """Compose node cards from resolved behavior and explicit collaborators."""

    _ICON_MAP = {
        "application": FIF.APPLICATION,
        "edit": FIF.EDIT,
        "eraser": AppIcon.ERASER_20_REGULAR,
        "folder": FIF.FOLDER,
        "model": AppIcon.BRAIN_CIRCUIT_20_REGULAR,
        "palette": FIF.PALETTE,
        "photo": FIF.PHOTO,
    }

    def __init__(
        self,
        panel: Any,
        services: EditorPanelServiceBundle,
        model_choice_snapshot_controller: PanelModelChoiceSnapshotController
        | None = None,
        dimension_preset_source: DimensionPresetMenuSource | None = None,
        node_input_preset_source: NodeInputPresetSource | None = None,
        prompt_segment_preset_source: PromptSegmentPresetSource | None = None,
    ) -> None:
        """Initialize card builder with its owning panel and live definition gateway."""

        self.panel = panel
        self._services = services
        self._model_choice_snapshot_controller = model_choice_snapshot_controller
        self._dimension_preset_source = dimension_preset_source
        self._node_input_preset_source = node_input_preset_source
        self._prompt_segment_preset_source = prompt_segment_preset_source
        self._field_rows = FieldRowBuilder(
            panel=panel,
            icon_builder=self.build_icon_widget,
            icon_resolver=self.get_icon_for_row,
            dimension_preset_source=dimension_preset_source,
        )
        self._body_composer = NodeCardBodyComposer(
            panel=panel,
            field_rows=self._field_rows,
        )

    def _snapshot_panel(self, cube_state: Any, alias: str | None) -> NodePanelSnapshot:
        """Capture the panel state needed while building one node card."""

        cube_id = getattr(cube_state, "cube_id", None)
        raw_cube_states = self.panel._cube_states or {}
        cube_states = raw_cube_states if isinstance(raw_cube_states, Mapping) else {}
        raw_stack_order = self.panel._stack_order or []
        stack_order = raw_stack_order if isinstance(raw_stack_order, Sequence) else ()
        return NodePanelSnapshot(
            cube_id=cube_id,
            current_alias=alias,
            cube_states=cube_states,
            stack_order=stack_order,
        )

    @staticmethod
    def _cube_buffer(cube_state: Any) -> dict[str, Any]:
        """Return the mutable cube buffer when present."""

        buffer = getattr(cube_state, "buffer", None)
        return buffer if isinstance(buffer, dict) else {}

    @staticmethod
    def _all_buffers_from_snapshot(
        snapshot: NodePanelSnapshot,
    ) -> dict[str, dict[str, Any]]:
        """Return stack-ordered cube buffers for initial link-selector setup."""

        return {
            alias: cube_state.buffer
            for alias in snapshot.stack_order
            if (cube_state := snapshot.cube_states.get(alias)) is not None
            and isinstance(getattr(cube_state, "buffer", None), dict)
        }

    def _wire_widget(
        self,
        widget: Any,
        cube_state: Any,
        metadata: dict[str, Any],
    ) -> None:
        """Delegate widget-state wiring to the field-state owner."""

        layout_changed = getattr(self.panel, "promptEditorLayoutChanged", None)
        emit_layout_changed = getattr(layout_changed, "emit", None)

        def emit_prompt_layout_changed() -> None:
            """Emit prompt layout change when a prompt editor height changes."""

            if callable(emit_layout_changed):
                emit_layout_changed()

        controller = getattr(self.panel, "_field_state_controller", None)
        if not isinstance(controller, EditorPanelFieldStateController):
            controller = EditorPanelFieldStateController(self.panel)
            setattr(self.panel, "_field_state_controller", controller)
        controller.bind_node_widget_state(
            widget,
            cube_state,
            metadata,
            manual_prompt_height_changed=emit_prompt_layout_changed
            if callable(emit_layout_changed)
            else None,
        )

    def get_icon_for_row(
        self, node_name: str, row_label: str, column_index: int | None = None
    ) -> FIF | None:
        """Return an optional Fluent icon for one grouped row slot."""

        _ = (node_name, row_label, column_index)
        return None

    def build_node_card(
        self,
        *,
        node_name: str,
        inputs: dict[str, Any],
        node_type: str,
        field_specs: Mapping[str, ResolvedFieldSpec],
        cube_state: Any,
        resolved_behavior: ResolvedNodeBehavior,
        display_decision: NodeDisplayDecision | None = None,
        alias: str | None = None,
        parent: QWidget | None = None,
        prompt_field_inputs: Mapping[str, NodeCardPromptFieldInputs] | None = None,
    ) -> QWidget | None:
        """Build one node card from explicit node behavior and current buffer state."""
        card_started_at = panel_projection_observability_started_at()
        wrapper: NodeCardWidget | None = None
        log_context = _NodeCardBuildLogContext(
            cube_alias=alias or "",
            node_name=node_name,
            node_class=node_type,
            field_spec_count=len(field_specs),
        )
        self._clear_field_widget_registrations_for_node(
            alias=alias,
            node_name=node_name,
        )
        if (
            resolved_behavior.card.hidden
            and display_decision is not None
            and not display_decision.revealable
        ):
            log_debug(
                _LOGGER,
                "Skipped hard-hidden editor node card",
                cube_alias=alias or "",
                node_name=node_name,
                node_class_type=node_type,
            )
            return None
        snapshot_started_at = panel_projection_observability_started_at()
        snapshot = self._snapshot_panel(cube_state, alias)
        _log_node_card_build_timing(
            "node_card.snapshot_panel",
            started_at=snapshot_started_at,
            context=log_context,
        )
        wrapper_parent = parent if parent is not None else self.panel
        wrapper = NodeCardWidget(wrapper_parent)
        node_card, node_card_layout, content_body, content_layout = (
            self._create_node_card_container(parent=wrapper)
        )
        input_keys = list(field_specs.keys())
        visible_keys = self._gather_visible_keys(
            input_keys=input_keys,
            resolved_behavior=resolved_behavior,
            skip_keys=set(),
        )
        allow_unbounded_content_height = (
            resolved_behavior.card.collapse_mode == CollapseMode.EXEMPT
        )
        node_card_variant = resolve_node_card_variant(resolved_behavior)
        is_subgraph_wrapper_card = self._is_subgraph_wrapper_card(field_specs)
        if is_subgraph_wrapper_card:
            log_debug(
                _LOGGER,
                "Building subgraph wrapper node card",
                cube_alias=alias or "",
                node_name=node_name,
                node_class=node_type,
                field_spec_keys=",".join(field_specs.keys()),
                visible_groups=";".join(",".join(group) for group in visible_keys),
                title_switch=bool(
                    display_decision is not None
                    and display_decision.show_enabled_switch
                ),
            )

        try:
            fields_started_at = panel_projection_observability_started_at()
            for key_group in visible_keys:
                if len(key_group) > 1:
                    widgets: list[tuple[str, QWidget]] = []
                    field_behaviors: dict[str, FieldBehavior] = {}
                    for key in key_group:
                        val = inputs.get(key)
                        if self.panel.is_connection(val):
                            self._log_wrapper_field_trace(
                                enabled=is_subgraph_wrapper_card,
                                alias=alias,
                                node_name=node_name,
                                key=key,
                                action="skip_connection",
                                field_spec=field_specs.get(key),
                            )
                            continue
                        field_behavior = resolved_behavior.fields.get(key)
                        if field_behavior is None:
                            self._log_wrapper_field_trace(
                                enabled=is_subgraph_wrapper_card,
                                alias=alias,
                                node_name=node_name,
                                key=key,
                                action="skip_missing_behavior",
                                field_spec=field_specs.get(key),
                            )
                            continue
                        self._log_wrapper_field_trace(
                            enabled=is_subgraph_wrapper_card,
                            alias=alias,
                            node_name=node_name,
                            key=key,
                            action="field_attempt",
                            field_spec=field_specs.get(key),
                        )
                        field = self._create_field_for_key(
                            node_name=node_name,
                            field_spec=field_specs[key],
                            content_body=content_body,
                            content_layout=content_layout,
                            allow_unbounded_content_height=(
                                allow_unbounded_content_height
                            ),
                            cube_state=cube_state,
                            alias=alias,
                            prompt_field_inputs=prompt_field_inputs,
                        )
                        if field is None or field is LAYOUT_HANDLED:
                            self._log_wrapper_field_trace(
                                enabled=is_subgraph_wrapper_card,
                                alias=alias,
                                node_name=node_name,
                                key=key,
                                action="layout_handled"
                                if field is LAYOUT_HANDLED
                                else "factory_none",
                                field_spec=field_specs.get(key),
                            )
                            continue
                        self._log_wrapper_field_trace(
                            enabled=is_subgraph_wrapper_card,
                            alias=alias,
                            node_name=node_name,
                            key=key,
                            action="widget_built",
                            field_spec=field_specs.get(key),
                            widget_type=field.__class__.__name__,
                        )
                        widgets.append((key, field))
                        field_behaviors[key] = field_behavior
                    if widgets:
                        self._body_composer.add_n_column_row(
                            fields=widgets,
                            field_behaviors=field_behaviors,
                            content_layout=content_layout,
                            node_name=node_name,
                        )
                    continue

                key = key_group[0]
                value = inputs.get(key)
                if self.panel.is_connection(value):
                    self._log_wrapper_field_trace(
                        enabled=is_subgraph_wrapper_card,
                        alias=alias,
                        node_name=node_name,
                        key=key,
                        action="skip_connection",
                        field_spec=field_specs.get(key),
                    )
                    continue
                field_behavior = resolved_behavior.fields.get(key)
                if field_behavior is None:
                    self._log_wrapper_field_trace(
                        enabled=is_subgraph_wrapper_card,
                        alias=alias,
                        node_name=node_name,
                        key=key,
                        action="skip_missing_behavior",
                        field_spec=field_specs.get(key),
                    )
                    continue
                self._log_wrapper_field_trace(
                    enabled=is_subgraph_wrapper_card,
                    alias=alias,
                    node_name=node_name,
                    key=key,
                    action="field_attempt",
                    field_spec=field_specs.get(key),
                )
                field = self._create_field_for_key(
                    node_name=node_name,
                    field_spec=field_specs[key],
                    content_body=content_body,
                    content_layout=content_layout,
                    allow_unbounded_content_height=allow_unbounded_content_height,
                    cube_state=cube_state,
                    alias=alias,
                    prompt_field_inputs=prompt_field_inputs,
                )
                if field is None or field is LAYOUT_HANDLED:
                    self._log_wrapper_field_trace(
                        enabled=is_subgraph_wrapper_card,
                        alias=alias,
                        node_name=node_name,
                        key=key,
                        action="layout_handled"
                        if field is LAYOUT_HANDLED
                        else "factory_none",
                        field_spec=field_specs.get(key),
                    )
                    continue
                self._log_wrapper_field_trace(
                    enabled=is_subgraph_wrapper_card,
                    alias=alias,
                    node_name=node_name,
                    key=key,
                    action="widget_built",
                    field_spec=field_specs.get(key),
                    widget_type=field.__class__.__name__,
                )
                self._add_input_row(
                    label=self._display_label_for_field(field_specs[key]),
                    widget=field,
                    field_behavior=field_behavior,
                    content_layout=content_layout,
                )
            _log_node_card_build_timing(
                "node_card.build_fields",
                started_at=fields_started_at,
                context=log_context,
                visible_group_count=len(visible_keys),
            )
        except Exception as error:
            log_warning(
                _LOGGER,
                "Discarded partial editor node card after field build failure",
                cube_alias=alias or "",
                node_name=node_name,
                node_class_type=node_type,
                error_type=type(error).__name__,
            )
            self._delete_unbuilt_node_card(wrapper)
            raise
        has_rows = content_layout.count() > 0
        has_title_controls = bool(resolved_behavior.card.title_controls) or bool(
            display_decision is not None and display_decision.show_enabled_switch
        )
        if not has_rows and not has_title_controls:
            if is_subgraph_wrapper_card:
                log_debug(
                    _LOGGER,
                    "Skipped empty subgraph wrapper node card",
                    cube_alias=alias or "",
                    node_name=node_name,
                    node_class=node_type,
                    has_rows=has_rows,
                    has_title_controls=has_title_controls,
                    field_spec_count=len(field_specs),
                    visible_group_count=len(visible_keys),
                )
            self._delete_unbuilt_node_card(wrapper)
            return None

        title_started_at = panel_projection_observability_started_at()
        title_row, chevron = self._create_title_row(
            node_name=node_name,
            node_type=node_type,
            inputs=inputs,
            field_specs=field_specs,
            resolved_behavior=resolved_behavior,
            display_decision=display_decision,
            snapshot=snapshot,
            no_chevron=(
                not has_rows
                or resolved_behavior.card.collapse_mode == CollapseMode.EXEMPT
            ),
            cube_state=cube_state,
            parent=node_card,
        )
        _log_node_card_build_timing(
            "node_card.create_title_row",
            started_at=title_started_at,
            context=log_context,
            has_rows=has_rows,
            has_title_controls=has_title_controls,
        )
        node_card_layout.addWidget(title_row)
        accordion_controller = None
        if has_rows:
            # This divider must live inside the content surface, not as a standalone
            # widget between the title and body. Standalone placement composites over
            # the transparent parent and renders darker than field-row dividers.
            content_layout.insertWidget(
                0,
                self._create_title_body_divider(content_body.content_widget()),
            )
            self._body_composer.reconcile_separator_visibility()
            content_body.set_content_height(content_layout.sizeHint().height())
            node_card_layout.addWidget(content_body)
            if resolved_behavior.card.collapse_mode != CollapseMode.EXEMPT:
                accordion_controller = self._setup_collapsible_animation(
                    card_title=title_row,
                    content_body=content_body,
                    content_layout=content_layout,
                    divider_below_title=None,
                    chevron=chevron,
                )
            else:
                set_accordion_surface_attachment(
                    card_title=title_row,
                    content_body=content_body,
                    attached=True,
                )
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(node_card)
        self._register_card_mode_binding(
            alias=alias,
            node_name=node_name,
            wrapper=wrapper,
            title_row=title_row,
            content_body=content_body if has_rows else None,
            content_layout=content_layout if has_rows else None,
            chevron=chevron,
            accordion_controller=accordion_controller,
            collapsible=(
                has_rows and resolved_behavior.card.collapse_mode != CollapseMode.EXEMPT
            ),
            has_rows=has_rows,
            allow_unbounded_content_height=allow_unbounded_content_height,
        )
        wrapper.setProperty("cube_alias", alias)
        wrapper.setProperty("node_name", node_name)
        wrapper.setProperty("node_class_type", node_type)
        wrapper.setProperty("node_card_variant", node_card_variant.value)
        wrapper.setProperty("has_title_controls", has_title_controls)
        wrapper.setProperty("base_card_visible", True)
        if parent is None:
            wrapper.setVisible(True)
        else:
            wrapper.setVisible(False)
        node_card.defer_model_picker_width_group_sync()
        if is_subgraph_wrapper_card:
            log_debug(
                _LOGGER,
                "Built subgraph wrapper node card",
                cube_alias=alias or "",
                node_name=node_name,
                node_class=node_type,
                has_rows=has_rows,
                has_title_controls=has_title_controls,
                content_row_count=content_layout.count(),
            )
        _log_node_card_build_timing(
            "node_card.built",
            started_at=card_started_at,
            context=log_context,
            visible_group_count=len(visible_keys),
            has_rows=has_rows,
            has_title_controls=has_title_controls,
        )
        return wrapper

    def _clear_field_widget_registrations_for_node(
        self,
        *,
        alias: str | None,
        node_name: str,
    ) -> None:
        """Remove stale field widget registrations owned by one node card render."""

        if alias is None:
            return

        removed_row_count = self._remove_node_field_keys(
            getattr(self.panel, "row_widgets", None),
            alias=alias,
            node_name=node_name,
        )
        removed_column_count = self._remove_node_field_keys(
            getattr(self.panel, "col_widgets", None),
            alias=alias,
            node_name=node_name,
        )
        field_registry = getattr(self.panel, "_field_registry", None)
        remove_registered_node = getattr(field_registry, "remove_node", None)
        removed_input_count = (
            int(remove_registered_node(alias, node_name))
            if callable(remove_registered_node)
            else self._remove_node_field_keys(
                getattr(self.panel, "input_widgets_by_field_key", None),
                alias=alias,
                node_name=node_name,
            )
        )
        if removed_row_count or removed_column_count or removed_input_count:
            log_debug(
                _LOGGER,
                "Cleared stale node-card field widget registrations",
                cube_alias=alias,
                node_name=node_name,
                removed_row_count=removed_row_count,
                removed_column_count=removed_column_count,
                removed_input_count=removed_input_count,
            )

    @classmethod
    def _remove_node_field_keys(
        cls,
        registry: object,
        *,
        alias: str,
        node_name: str,
    ) -> int:
        """Remove registry keys shaped as fields owned by one node card."""

        if not isinstance(registry, dict):
            return 0
        field_keys = [
            field_key
            for field_key in registry
            if cls._is_node_field_key(
                field_key,
                alias=alias,
                node_name=node_name,
            )
        ]
        for field_key in field_keys:
            registry.pop(field_key, None)
        return len(field_keys)

    @staticmethod
    def _is_node_field_key(
        field_key: object,
        *,
        alias: str,
        node_name: str,
    ) -> bool:
        """Return whether one registry key belongs to one node card."""

        return bool(
            isinstance(field_key, tuple)
            and len(field_key) >= 3
            and field_key[0] == alias
            and field_key[1] == node_name
        )

    def _register_card_mode_binding(
        self,
        *,
        alias: str | None,
        node_name: str,
        wrapper: QWidget,
        title_row: QWidget,
        content_body: QWidget | None,
        content_layout: QVBoxLayout | None,
        chevron: AccordionChevronWidget | None,
        accordion_controller: AccordionMotionController | None,
        collapsible: bool,
        has_rows: bool,
        allow_unbounded_content_height: bool,
    ) -> None:
        """Register a card's mode-controlled widgets with the owning panel."""

        controller = getattr(self.panel, "_node_card_mode_controller", None)
        register = getattr(controller, "register", None)
        if not callable(register):
            return
        enabled_switch_wrapper = getattr(title_row, "_enabled_switch_wrapper", None)
        enabled_switch = getattr(title_row, "_enabled_switch_widget", None)
        register(
            alias,
            node_name,
            NodeCardModeBinding(
                wrapper=wrapper,
                title_row=title_row,
                content_body=content_body,
                content_layout=content_layout,
                chevron=chevron,
                enabled_switch_wrapper=enabled_switch_wrapper
                if isinstance(enabled_switch_wrapper, QWidget)
                else None,
                enabled_switch=enabled_switch,
                accordion_controller=accordion_controller,
                collapsible=collapsible,
                has_rows=has_rows,
                allow_unbounded_content_height=allow_unbounded_content_height,
            ),
        )

    def _add_input_row(
        self,
        *,
        label: str,
        widget: QWidget,
        field_behavior: FieldBehavior,
        content_layout: QVBoxLayout,
    ) -> None:
        """Add one input row through the shared row builder."""

        self._body_composer.add_input_row(
            label=label,
            widget=widget,
            field_behavior=field_behavior,
            content_layout=content_layout,
        )

    def add_n_column_row(
        self,
        *,
        fields: list[tuple[str, QWidget]],
        field_behaviors: Mapping[str, FieldBehavior],
        content_layout: QVBoxLayout,
        node_name: str = "",
    ) -> None:
        """Add one grouped multi-column row through the shared row builder."""

        self._body_composer.add_n_column_row(
            fields=fields,
            field_behaviors=field_behaviors,
            content_layout=content_layout,
            node_name=node_name,
        )

    def _gather_visible_keys(
        self,
        *,
        input_keys: list[str],
        resolved_behavior: ResolvedNodeBehavior,
        skip_keys: set[str],
    ) -> list[list[str]]:
        """Delegate visible-field grouping rules to the row-builder collaborator."""

        return self._field_rows.gather_visible_keys(
            input_keys=input_keys,
            field_groups=resolved_behavior.field_groups,
            skip_keys=skip_keys,
        )

    @staticmethod
    def _is_subgraph_wrapper_card(
        field_specs: Mapping[str, ResolvedFieldSpec],
    ) -> bool:
        """Return whether the field specs belong to a subgraph wrapper card."""

        return any(
            field_spec.meta_info.get("subgraph_wrapper") is True
            for field_spec in field_specs.values()
        )

    @staticmethod
    def _log_wrapper_field_trace(
        *,
        enabled: bool,
        alias: str | None,
        node_name: str,
        key: str,
        action: str,
        field_spec: ResolvedFieldSpec | None,
        widget_type: str = "",
    ) -> None:
        """Log wrapper field instrumentation for projection diagnostics."""

        if not enabled:
            return
        log_debug(
            _LOGGER,
            "Handled subgraph wrapper node-card field",
            cube_alias=alias or "",
            node_name=node_name,
            field_key=key,
            action=action,
            widget_type=widget_type,
            field_type=field_spec.field_type if field_spec is not None else "",
            raw_value_present=field_spec.raw_value is not None
            if field_spec is not None
            else "",
            default="default" in field_spec.meta_info if field_spec is not None else "",
            value_source=(
                field_spec.value_source.value if field_spec is not None else ""
            ),
        )

    @staticmethod
    def _display_label_for_field(field_spec: ResolvedFieldSpec) -> str:
        """Return the public field label when wrapper metadata provides one."""

        for metadata_key in ("label", "localized_name"):
            metadata_value = field_spec.meta_info.get(metadata_key)
            if isinstance(metadata_value, str):
                stripped = metadata_value.strip()
                if stripped:
                    return stripped
        return field_spec.field_key

    def _create_field_for_key(
        self,
        *,
        node_name: str,
        field_spec: ResolvedFieldSpec,
        content_body: QWidget | None,
        content_layout: QVBoxLayout | None,
        allow_unbounded_content_height: bool,
        cube_state: Any,
        alias: str | None,
        prompt_field_inputs: Mapping[str, NodeCardPromptFieldInputs] | None = None,
    ) -> Any:
        """Build one field widget from resolved field behavior and live definitions."""
        field_started_at = panel_projection_observability_started_at()
        key = field_spec.field_key
        extended_meta = dict(field_spec.meta_info)
        extended_meta["cube_alias"] = alias
        cube_buffer = self._cube_buffer(cube_state)
        node_data = cube_buffer.get("nodes", {}).get(node_name)
        if isinstance(node_data, dict):
            extended_meta["node_data"] = node_data
        factory_started_at = panel_projection_observability_started_at()
        is_prompt_field = (
            field_spec.field_behavior.presentation == FieldPresentation.PROMPT_BOX
        )
        log_context = _NodeCardFieldLogContext(
            cube_alias=alias or "",
            node_name=node_name,
            node_class=field_spec.class_type,
            field_key=key,
            field_type=field_spec.field_type or "",
            presentation=field_spec.field_behavior.presentation.value,
        )
        prepared_prompt_inputs = (
            prompt_field_inputs.get(key)
            if is_prompt_field and prompt_field_inputs is not None
            else None
        )
        scheduled_lora_resolver = (
            prepared_prompt_inputs.scheduled_lora_resolver
            if prepared_prompt_inputs is not None
            else None
        )
        prompt_feature_profile = (
            prepared_prompt_inputs.prompt_field_profile.feature_profile
            if prepared_prompt_inputs is not None
            and prepared_prompt_inputs.prompt_field_profile is not None
            else None
        )
        prompt_syntax_profile = (
            prepared_prompt_inputs.prompt_field_profile.syntax_profile
            if prepared_prompt_inputs is not None
            and prepared_prompt_inputs.prompt_field_profile is not None
            else None
        )
        try:
            prompt_services = self._services.prompt
            prompt_runtime = prompt_services.runtime
            result = build_widget_for_field_spec(
                parent=self.panel,
                field_spec=ResolvedFieldSpec(
                    cube_alias=field_spec.cube_alias,
                    node_name=field_spec.node_name,
                    class_type=field_spec.class_type,
                    field_key=field_spec.field_key,
                    field_type=field_spec.field_type,
                    constraints=dict(field_spec.constraints),
                    meta_info=extended_meta,
                    field_info=list(field_spec.field_info)
                    if field_spec.field_info is not None
                    else None,
                    value=field_spec.value,
                    field_behavior=field_spec.field_behavior,
                    raw_value=field_spec.raw_value,
                    value_source=field_spec.value_source,
                ),
                prompt_autocomplete_gateway=prompt_runtime.autocomplete_gateway,
                prompt_wildcard_catalog_gateway=(
                    prompt_runtime.wildcard_catalog_gateway
                ),
                danbooru_url_import_service=(
                    prompt_runtime.danbooru_url_import_service
                ),
                danbooru_wiki_service=prompt_runtime.danbooru_wiki_service,
                danbooru_image_preview_service=(
                    prompt_runtime.danbooru_image_preview_service
                ),
                danbooru_recent_posts_service=(
                    prompt_runtime.danbooru_recent_posts_service
                ),
                prompt_lora_catalog_service=prompt_runtime.lora_catalog_service,
                prompt_scheduled_lora_service=(
                    prompt_runtime.scheduled_lora_service_or_default()
                ),
                scheduled_lora_resolver=scheduled_lora_resolver,
                prompt_feature_profile=prompt_feature_profile,
                prompt_syntax_profile=prompt_syntax_profile,
                prompt_segment_preset_source=self._prompt_segment_preset_source,
                prompt_spellcheck_service=prompt_runtime.spellcheck_service,
                model_choice_snapshot_controller=self._model_choice_snapshot_controller,
                thumbnail_asset_repository=(
                    self._services.model.thumbnail_asset_repository
                ),
                model_metadata_action_handler=(
                    self._services.model.model_metadata_action_handler
                    or prompt_runtime.model_metadata_action_handler
                ),
                node_definition_gateway=self._services.node_definition_gateway,
                prompt_task_executor_factory=(
                    prompt_runtime.prompt_task_executor_factory
                ),
                danbooru_lookup_dispatcher_factory=(
                    prompt_runtime.danbooru_lookup_dispatcher_factory
                ),
                model_picker_thumbnail_preload_route_factory=(
                    prompt_services.model_picker_thumbnail_preload_route_factory
                ),
            )
        except (RuntimeError, TypeError, ValueError) as error:
            if field_spec.meta_info.get("subgraph_wrapper") is True:
                log_warning(
                    _LOGGER,
                    "Subgraph wrapper field widget build failed",
                    cube_alias=alias or "",
                    node_name=node_name,
                    field_key=key,
                    field_type=field_spec.field_type or "",
                    value_source=field_spec.value_source.value,
                    error_type=type(error).__name__,
                )
            raise
        _log_node_card_field_timing(
            "node_card.field_factory",
            started_at=factory_started_at,
            context=log_context,
            result_type=type(result).__name__ if result is not None else "None",
        )
        if result is None or result is LAYOUT_HANDLED:
            return result
        widget = result[0] if isinstance(result, tuple) else result
        field_tooltip = tooltip_from_field_meta(field_spec.meta_info)
        metadata = {
            "cube_alias": alias,
            "node_name": node_name,
            "key": key,
            "type": field_spec.field_type,
            "meta_info": dict(field_spec.meta_info),
            "field_info": field_spec.field_info,
            "constraints": dict(field_spec.constraints),
            "node_type": field_spec.class_type,
            "tooltip": field_tooltip,
            "resolved_value": field_spec.value,
            "value_source": field_spec.value_source.value,
        }
        safe_metadata = sanitation.deep_sanitize_for_qt(metadata)
        widget.setProperty("input_metadata", safe_metadata)
        configure_wheel_intent = getattr(
            self.panel,
            "configure_wheel_intent_for_widget",
            None,
        )
        if callable(configure_wheel_intent):
            configure_wheel_intent(widget)
        if field_spec.field_behavior.label_override:
            widget.setProperty(
                "label_override",
                field_spec.field_behavior.label_override,
            )
        if field_spec.field_behavior.column_span is not None:
            widget.setProperty(
                "column_span",
                field_spec.field_behavior.column_span,
            )
        wiring_started_at = panel_projection_observability_started_at()
        self._wire_widget(widget, cube_state, metadata)
        _log_node_card_field_timing(
            "node_card.field_wired",
            started_at=wiring_started_at,
            context=log_context,
            widget_type=widget.__class__.__name__,
        )
        if alias is not None:
            binding = EditorFieldBinding.from_widget(widget)
            register_field = getattr(
                getattr(self.panel, "_field_registry", None),
                "register",
                None,
            )
            if binding is not None and callable(register_field):
                register_field(binding, widget)
            elif hasattr(self.panel, "input_widgets_by_field_key"):
                self.panel.input_widgets_by_field_key[(alias, node_name, key)] = widget
        widget_wiring.bind_picker_signals(
            widget,
            self.panel,
            cube_alias=alias,
            node_name=node_name,
        )
        if content_body is not None and content_layout is not None:
            bind_field_widget_card_relayout(
                field_widget=widget,
                content_body=content_body,
                content_layout=content_layout,
                allow_unbounded_height=allow_unbounded_content_height,
            )
        _log_node_card_field_timing(
            "node_card.field_prepared",
            started_at=field_started_at,
            context=log_context,
            widget_type=widget.__class__.__name__,
        )
        return widget

    def _create_node_card_container(
        self,
        *,
        parent: QWidget,
    ) -> tuple[_NodeCardSurface, QVBoxLayout, AccordionContentClip, QVBoxLayout]:
        """Create the outer card widget and inner collapsible content container."""

        node_card = _NodeCardSurface(parent)
        node_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        node_card_layout = create_vbox(
            parent=node_card, margins=(0, 0, 0, 0), spacing=0
        )
        content_body = AccordionContentClip(
            parent=node_card,
            content_surface_factory=_NodeCardContentSurface,
        )
        content_body.setObjectName("NodeCardContentClip")
        content_surface = content_body.content_widget()
        content_layout = create_vbox(
            parent=content_surface,
            margins=(0, NODE_CARD_BODY_TOP_PADDING, 0, NODE_CARD_BODY_BOTTOM_PADDING),
            spacing=NODE_CARD_BODY_ROW_SPACING,
        )
        return node_card, node_card_layout, content_body, content_layout

    def _delete_unbuilt_node_card(self, wrapper: QWidget | None) -> None:
        """Synchronously remove a card root that will not be returned to a layout."""

        if wrapper is None:
            return
        try:
            wrapper.hide()
            delete(wrapper)
        except RuntimeError:
            return

    def build_icon_widget(
        self,
        icon_enum: FIF | None,
        parent: QWidget | None = None,
    ) -> QWidget:
        """Return an IconWidget if icon_enum is set, else a fixed-size spacer widget."""

        widget_parent = parent if parent is not None else self.panel
        if icon_enum:
            icon = IconWidget(icon_enum, widget_parent)
            icon.setFixedSize(EDITOR_ROW_ICON_SIZE, EDITOR_ROW_ICON_SIZE)
            return icon
        spacer = QWidget(widget_parent)
        spacer.setFixedSize(EDITOR_ROW_ICON_SIZE, EDITOR_ROW_ICON_SIZE)
        return spacer

    def _build_title_icon_widget(
        self,
        icon_enum: Any | None,
        *,
        parent: QWidget,
    ) -> QWidget:
        """Return a fixed title-icon slot with the icon centered inside it."""

        slot = QWidget(parent)
        slot.setObjectName("NodeCardTitleIconSlot")
        slot.setFixedSize(
            NODE_CARD_TITLE_ICON_SLOT_SIZE,
            NODE_CARD_TITLE_ICON_SLOT_SIZE,
        )
        if icon_enum is None:
            return slot

        icon = IconWidget(icon_enum, slot)
        icon.setObjectName("NodeCardTitleIcon")
        icon.setFixedSize(NODE_CARD_TITLE_ICON_SIZE, NODE_CARD_TITLE_ICON_SIZE)

        slot_layout = QHBoxLayout(slot)
        slot_layout.setContentsMargins(0, 0, 0, 0)
        slot_layout.setSpacing(0)
        slot_layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignCenter)
        return slot

    def _resolve_title_icon(self, icon_name: str | None) -> Any | None:
        """Return the mapped Fluent icon for one behavior icon name."""

        return self._ICON_MAP.get(icon_name) if isinstance(icon_name, str) else None

    def _create_title_row(
        self,
        *,
        node_name: str,
        resolved_behavior: ResolvedNodeBehavior,
        display_decision: NodeDisplayDecision | None,
        snapshot: NodePanelSnapshot,
        no_chevron: bool,
        cube_state: Any,
        parent: QWidget | None = None,
        node_type: str = "",
        inputs: Mapping[str, object] | None = None,
        field_specs: Mapping[str, ResolvedFieldSpec] | None = None,
    ) -> tuple[QWidget, AccordionChevronWidget | None]:
        """Build the title row from resolved card behavior."""

        card_parent = parent if parent is not None else self.panel
        card_title = _NodeCardHeaderSurface(card_parent)
        card_title.setFixedHeight(NODE_CARD_TITLE_HEIGHT)
        title_layout = QHBoxLayout(card_title)
        title_layout.setContentsMargins(
            EDITOR_ROW_HORIZONTAL_MARGINS[0],
            _NODE_CARD_SURFACE_VERTICAL_PADDING,
            EDITOR_ROW_HORIZONTAL_MARGINS[2],
            _NODE_CARD_SURFACE_VERTICAL_PADDING,
        )
        title_layout.setSpacing(EDITOR_ROW_SPACING)

        title_icon = self._build_title_icon_widget(
            self._resolve_title_icon(resolved_behavior.card.icon_name),
            parent=card_title,
        )
        title_tooltip = normalized_tooltip(resolved_behavior.card.tooltip)
        title_layout.addWidget(title_icon)

        display_name = (
            resolved_behavior.display_name.strip()
            if isinstance(resolved_behavior.display_name, str)
            else ""
        )
        title_label = CaptionLabel(
            literal_label_text(display_name or beautify_label(node_name))
        )
        setFont(title_label, 14, QFont.DemiBold)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        bind_fluent_tooltip(
            card_title,
            title_tooltip,
            card_title,
            title_icon,
            title_label,
            show_delay_ms=600,
        )
        card_title.set_interactive_targets((title_icon, title_label))
        if inputs is not None and field_specs is not None:
            self._bind_node_input_preset_menu(
                title_row=card_title,
                node_name=node_name,
                node_type=node_type,
                inputs=inputs,
                field_specs=field_specs,
                cube_state=cube_state,
                cube_alias=snapshot.current_alias,
            )

        if (
            TitleControl.NODE_LINK_SELECTOR in resolved_behavior.card.title_controls
            or TitleControl.PROMPT_LINK_SELECTOR
            in resolved_behavior.card.title_controls
        ):
            behavior_snapshot = self.panel.current_behavior_snapshot()
            endpoint_index = (
                behavior_snapshot.node_link_endpoint_index
                if behavior_snapshot is not None
                else None
            )
            if endpoint_index is not None and snapshot.current_alias is not None:
                endpoint = self._title_node_link_endpoint(
                    endpoint_index=endpoint_index,
                    cube_alias=snapshot.current_alias,
                    node_name=node_name,
                    resolved_behavior=resolved_behavior,
                )
                if endpoint is not None:
                    meta_registry = getattr(self.panel, "meta_registry", None)
                    register_title_surface = getattr(
                        meta_registry,
                        "register_node_link_title_surface",
                        None,
                    )
                    if callable(register_title_surface):
                        register_title_surface(
                            cube_alias=snapshot.current_alias,
                            node_name=node_name,
                            identity=endpoint.identity,
                            title_layout=title_layout,
                            title_controls=resolved_behavior.card.title_controls,
                        )
                    update_node_link_widgets_for_cube = getattr(
                        meta_registry,
                        "update_node_link_widgets_for_cube",
                        None,
                    )
                    if callable(update_node_link_widgets_for_cube):
                        update_node_link_widgets_for_cube(snapshot.current_alias)

        enabled_switch_wrapper = None
        if display_decision is not None and display_decision.show_enabled_switch:
            enabled_switch_wrapper = build_enabled_switch(
                card_title,
                snapshot.current_alias,
                node_name,
                cube_state,
                display_decision,
                checked_changed_callback=partial(
                    _apply_node_activation_change,
                    self.panel,
                    self._services,
                    cube_state,
                    node_name,
                    display_decision,
                ),
            )
            title_layout.addWidget(enabled_switch_wrapper)

        setattr(card_title, "_enabled_switch_wrapper", enabled_switch_wrapper)
        setattr(
            card_title,
            "_enabled_switch_widget",
            getattr(enabled_switch_wrapper, "_enabled_switch_widget", None),
        )
        apply_title_row_interaction(
            title_row=card_title,
            accordion_callback=None,
            enabled_switch=getattr(card_title, "_enabled_switch_widget", None),
            enabled_switch_wrapper=enabled_switch_wrapper,
        )

        if no_chevron:
            return card_title, None

        chevron = AccordionChevronWidget(card_title)
        title_layout.addWidget(chevron)
        card_title.set_interactive_targets((title_icon, title_label, chevron))
        return card_title, chevron

    def _bind_node_input_preset_menu(
        self,
        *,
        title_row: QWidget,
        node_name: str,
        node_type: str,
        inputs: Mapping[str, object],
        field_specs: Mapping[str, ResolvedFieldSpec],
        cube_state: Any,
        cube_alias: str | None,
    ) -> None:
        """Bind node input preset actions to the title row when available."""

        prepare_menu = getattr(
            self._node_input_preset_source,
            "prepare_node_input_preset_menu_model",
            None,
        )
        if callable(prepare_menu):
            prepare_menu(node_type=node_type, reason="node_card_built")
        is_connection = getattr(self.panel, "is_connection", None)
        if not callable(is_connection):
            return
        input_widgets = getattr(self.panel, "input_widgets_by_field_key", {})
        if not isinstance(input_widgets, Mapping):
            input_widgets = {}
        bind_node_title_preset_actions(
            title_row=title_row,
            context=NodeInputPresetContext(
                cube_alias=cube_alias,
                node_name=node_name,
                node_type=node_type,
                inputs=inputs,
                field_specs=field_specs,
                cube_state=cube_state,
                input_widgets_by_field_key=input_widgets,
            ),
            preset_source=self._node_input_preset_source,
            dialog_parent=self._preset_dialog_parent,
            is_connection=is_connection,
        )

    def _preset_dialog_parent(self) -> QWidget:
        """Return the widget that should own node preset save modals."""

        return self.panel if isinstance(self.panel, QWidget) else QWidget()

    def _create_title_body_divider(self, parent: QWidget) -> QWidget:
        """Create the shared divider between the title row and body rows."""

        divider = self._field_rows.make_horizontal_divider(parent)
        divider.setObjectName("NodeCardTitleBodyDivider")
        divider.setProperty("title_body_divider", True)
        return divider

    @staticmethod
    def _title_node_link_endpoint(
        *,
        endpoint_index: Any,
        cube_alias: str,
        node_name: str,
        resolved_behavior: ResolvedNodeBehavior,
    ) -> Any | None:
        """Return the node-link endpoint controlled by this title row."""

        if TitleControl.PROMPT_LINK_SELECTOR in resolved_behavior.card.title_controls:
            prompt_roles = [
                field_behavior.prompt.role
                for field_behavior in resolved_behavior.fields.values()
                if field_behavior.prompt is not None and field_behavior.prompt.linkable
            ]
            if len(prompt_roles) != 1:
                return None
            endpoint = endpoint_index.prompt_endpoint_for(cube_alias, prompt_roles[0])
            if endpoint is not None and endpoint.node_name == node_name:
                return endpoint
            return None
        for identity in endpoint_index.identities_for_cube(cube_alias):
            endpoint = endpoint_index.endpoint_for(cube_alias, identity)
            if endpoint is not None and endpoint.node_name == node_name:
                return endpoint
        return None

    def _setup_collapsible_animation(
        self,
        *,
        card_title: QWidget,
        content_body: AccordionContentClip,
        content_layout: QVBoxLayout,
        divider_below_title: QWidget | None,
        chevron: AccordionChevronWidget | None,
    ) -> AccordionMotionController | None:
        """Add toggleable collapse/expand animation to a node card."""

        if chevron is None:
            return None

        def update_owner_cube_height() -> None:
            """Refresh the owning cube wrapper height when accordion geometry changes."""

            parent = card_title.parentWidget()
            while parent is not None:
                if hasattr(parent, "update_cube_height"):
                    parent.update_cube_height()
                    return
                parent = parent.parentWidget()

        controller = AccordionMotionController(
            owner=self.panel,
            card_title=card_title,
            content_body=content_body,
            content_layout=content_layout,
            divider_below_title=divider_below_title,
            chevron=chevron,
            cube_height_updater=update_owner_cube_height,
        )
        setattr(content_body, "_accordion_motion_controller", controller)

        apply_title_row_interaction(
            title_row=card_title,
            accordion_callback=controller.toggle,
            enabled_switch=getattr(card_title, "_enabled_switch_widget", None),
            enabled_switch_wrapper=getattr(card_title, "_enabled_switch_wrapper", None),
        )
        return controller


__all__ = [
    "NodeCardBodyComposer",
    "NodeCardBuilder",
    "NodeCardPromptFieldInputs",
    "NodePanelSnapshot",
]
