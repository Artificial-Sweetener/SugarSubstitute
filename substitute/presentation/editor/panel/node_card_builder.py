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

from collections.abc import Mapping
from typing import Any, cast

from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]
from qfluentwidgets import IconWidget


from substitute.application.node_behavior import (
    CollapseMode,
    FieldBehavior,
    NodeDisplayDecision,
    ResolvedFieldSpec,
    ResolvedNodeBehavior,
)
from substitute.presentation.editor.field_actions import FieldActionContribution
from .node_card.advanced_input_binding import AdvancedInputCardBinding
from .node_card.body_composer import NodeCardBodyComposer
from .node_card.body_contribution import (
    NodeCardBodyContributionContext,
    NodeCardBodyContributor,
)
from .node_card.build_observability import (
    NodeCardBuildLogContext,
    log_node_card_build_timing,
    log_wrapper_field_trace,
)
from .node_card.field_realizer import NodeCardFieldRealizer
from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalogSource,
)
from .node_card.panel_snapshot import (
    NodePanelSnapshot,
    capture_node_panel_snapshot,
)
from .node_card.title_composer import NodeCardTitleComposer
from .node_card.surface_composer import (
    NodeCardSurfaceComposer,
    NodeCardSurfaceMetadata,
)
from .node_card.variant import resolve_node_card_variant
from substitute.presentation.editor.panel.menus.node_input_preset_menu_source import (
    NodeInputPresetSource,
)
from substitute.presentation.editor.panel.node_presentation_adapter import (
    build_node_presentation_request,
)
from substitute.presentation.editor.panel.node_presentation_binding import (
    NodeTitleTextTarget,
)
from substitute.presentation.editor.panel.factories.field_pipeline import (
    LAYOUT_HANDLED,
)
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshotController,
)
from substitute.presentation.editor.panel.node_card_build_transaction import (
    NodeCardBuildTransaction,
)
from substitute.presentation.editor.panel.prompt.field_inputs import (
    NodeCardPromptFieldInputs,
)
from substitute.presentation.editor.panel.projection_observability import (
    panel_projection_observability_started_at,
)
from substitute.presentation.editor.panel.service_bundle import EditorPanelServiceBundle
from substitute.presentation.editor.panel.widgets.field_row import FieldRowBuilder
from substitute.presentation.editor.panel.widgets.field_row_geometry import (
    EDITOR_ROW_ICON_SIZE,
)
from substitute.presentation.editor.panel.widgets.field_row_models import BuiltFieldRow
from substitute.presentation.editor.panel.widgets.node_card import NodeCardWidget
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetSource,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_warning,
)

_LOGGER = get_logger("presentation.editor.panel.node_card_builder")


class NodeCardBuilder:
    """Compose node cards from resolved behavior and explicit collaborators."""

    def __init__(
        self,
        panel: Any,
        services: EditorPanelServiceBundle,
        model_choice_snapshot_controller: PanelModelChoiceSnapshotController
        | None = None,
        dimension_preset_source: DimensionPresetCatalogSource | None = None,
        node_input_preset_source: NodeInputPresetSource | None = None,
        prompt_segment_preset_source: PromptSegmentPresetSource | None = None,
        body_contributors: tuple[NodeCardBodyContributor, ...] = (),
    ) -> None:
        """Initialize card builder with its owning panel and live definition gateway."""

        self.panel = panel
        self._services = services
        self._dimension_preset_source = dimension_preset_source
        self._node_input_preset_source = node_input_preset_source
        self._body_contributors = body_contributors
        self._field_realizer = NodeCardFieldRealizer(
            panel=panel,
            services=services,
            model_choice_snapshot_controller=model_choice_snapshot_controller,
            prompt_segment_preset_source=prompt_segment_preset_source,
        )
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
        self._surface_composer = NodeCardSurfaceComposer(
            panel=panel,
            node_presentation_service=services.node_presentation_service,
            divider_factory=self._field_rows.make_horizontal_divider,
            reconcile_separators=self._body_composer.reconcile_separator_visibility,
        )
        self._title_composer = NodeCardTitleComposer(
            panel=panel,
            services=services,
            node_input_preset_source=node_input_preset_source,
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
        log_context = NodeCardBuildLogContext(
            cube_alias=alias or "",
            node_name=node_name,
            node_class=node_type,
            field_spec_count=len(field_specs),
        )
        build_transaction = NodeCardBuildTransaction(
            panel=self.panel,
            cube_alias=alias,
            node_name=node_name,
        )
        cleanup = build_transaction.replace_existing()
        if cleanup.removed_any:
            log_debug(
                _LOGGER,
                "Cleared stale node-card field widget registrations",
                cube_alias=alias or "",
                node_name=node_name,
                removed_row_count=cleanup.row_count,
                removed_column_count=cleanup.column_count,
                removed_input_count=cleanup.input_count,
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
        snapshot = capture_node_panel_snapshot(
            panel=self.panel,
            cube_state=cube_state,
            alias=alias,
        )
        presentation_request = build_node_presentation_request(
            node_definition_gateway=self._services.node_definition_gateway,
            node_name=node_name,
            node_type=node_type,
            field_specs=field_specs,
            resolved_behavior=resolved_behavior,
        )
        node_presentation = self._services.node_presentation_service.present(
            presentation_request
        )
        log_node_card_build_timing(
            "node_card.snapshot_panel",
            started_at=snapshot_started_at,
            context=log_context,
        )
        wrapper_parent = parent if parent is not None else self.panel
        surface = self._surface_composer.create(
            parent=wrapper_parent,
            presentation_request=presentation_request,
            show_immediately=parent is None,
        )
        wrapper = surface.wrapper
        presentation_binding = surface.presentation_binding
        node_card = surface.card
        content_body = surface.content_body
        content_layout = surface.content_layout
        contribution_context = NodeCardBodyContributionContext(
            section_key=alias or "",
            node_name=node_name,
            node_type=node_type,
            inputs=inputs,
            graph=self._cube_buffer(cube_state),
        )
        contributions = tuple(
            contribution
            for contributor in self._body_contributors
            if (
                contribution := contributor.build(
                    contribution_context,
                )
            )
            is not None
        )
        input_keys = list(field_specs.keys())
        visible_keys = self._gather_visible_keys(
            input_keys=input_keys,
            resolved_behavior=resolved_behavior,
            skip_keys=set(),
            preferred_field_groups=tuple(
                contribution.field_keys for contribution in contributions
            ),
        )
        allow_unbounded_content_height = (
            resolved_behavior.card.collapse_mode == CollapseMode.EXEMPT
        )
        node_card_variant = resolve_node_card_variant(resolved_behavior)
        is_subgraph_wrapper_card = self._is_subgraph_wrapper_card(field_specs)
        field_action_contributions: list[FieldActionContribution] = []
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
                            log_wrapper_field_trace(
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
                            log_wrapper_field_trace(
                                enabled=is_subgraph_wrapper_card,
                                alias=alias,
                                node_name=node_name,
                                key=key,
                                action="skip_missing_behavior",
                                field_spec=field_specs.get(key),
                            )
                            continue
                        log_wrapper_field_trace(
                            enabled=is_subgraph_wrapper_card,
                            alias=alias,
                            node_name=node_name,
                            key=key,
                            action="field_attempt",
                            field_spec=field_specs.get(key),
                        )
                        field = self._field_realizer.realize(
                            node_name=node_name,
                            field_spec=field_specs[key],
                            content_body=content_body,
                            content_layout=content_layout,
                            allow_unbounded_content_height=(
                                allow_unbounded_content_height
                            ),
                            cube_state=cube_state,
                            alias=alias,
                            build_transaction=build_transaction,
                            prompt_field_inputs=prompt_field_inputs,
                            field_presentation=node_presentation.fields[key],
                        )
                        if field is None or field is LAYOUT_HANDLED:
                            log_wrapper_field_trace(
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
                        log_wrapper_field_trace(
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
                        widget_keys = frozenset(key for key, _widget in widgets)
                        contribution = next(
                            (
                                candidate
                                for candidate in contributions
                                if candidate.claimed_field_keys == widget_keys
                            ),
                            None,
                        )
                        built_row = self._body_composer.add_n_column_row(
                            fields=widgets,
                            field_behaviors=field_behaviors,
                            content_layout=content_layout,
                            node_name=node_name,
                            field_labels={
                                key: node_presentation.fields[key].label
                                for key, _widget in widgets
                            },
                            contribution=contribution,
                        )
                        presentation_binding.add_field_targets(built_row.text_targets)
                        field_action_contributions.extend(
                            built_row.action_contributions
                        )
                    continue

                key = key_group[0]
                value = inputs.get(key)
                if self.panel.is_connection(value):
                    log_wrapper_field_trace(
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
                    log_wrapper_field_trace(
                        enabled=is_subgraph_wrapper_card,
                        alias=alias,
                        node_name=node_name,
                        key=key,
                        action="skip_missing_behavior",
                        field_spec=field_specs.get(key),
                    )
                    continue
                log_wrapper_field_trace(
                    enabled=is_subgraph_wrapper_card,
                    alias=alias,
                    node_name=node_name,
                    key=key,
                    action="field_attempt",
                    field_spec=field_specs.get(key),
                )
                field = self._field_realizer.realize(
                    node_name=node_name,
                    field_spec=field_specs[key],
                    content_body=content_body,
                    content_layout=content_layout,
                    allow_unbounded_content_height=allow_unbounded_content_height,
                    cube_state=cube_state,
                    alias=alias,
                    build_transaction=build_transaction,
                    prompt_field_inputs=prompt_field_inputs,
                    field_presentation=node_presentation.fields[key],
                )
                if field is None or field is LAYOUT_HANDLED:
                    log_wrapper_field_trace(
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
                log_wrapper_field_trace(
                    enabled=is_subgraph_wrapper_card,
                    alias=alias,
                    node_name=node_name,
                    key=key,
                    action="widget_built",
                    field_spec=field_specs.get(key),
                    widget_type=field.__class__.__name__,
                )
                built_row = self._add_input_row(
                    label=node_presentation.fields[key].label,
                    widget=field,
                    field_behavior=field_behavior,
                    content_layout=content_layout,
                )
                presentation_binding.add_field_targets(built_row.text_targets)
                field_action_contributions.extend(built_row.action_contributions)
            log_node_card_build_timing(
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
            build_transaction.discard(wrapper)
            raise
        advanced_input_binding = AdvancedInputCardBinding.create(
            panel=self.panel,
            wrapper=wrapper,
            card_surface=node_card,
            content_body=content_body,
            content_layout=content_layout,
            editor_state=cube_state,
            alias=alias,
            node_name=node_name,
            field_specs=field_specs,
            allow_unbounded_height=allow_unbounded_content_height,
        )
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
            build_transaction.discard(wrapper)
            return None

        title_started_at = panel_projection_observability_started_at()
        title_row, chevron = self._title_composer.create(
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
            node_presentation=node_presentation,
            advanced_input_binding=advanced_input_binding,
            field_action_contributions=tuple(field_action_contributions),
        )
        log_node_card_build_timing(
            "node_card.create_title_row",
            started_at=title_started_at,
            context=log_context,
            has_rows=has_rows,
            has_title_controls=has_title_controls,
        )
        if advanced_input_binding is not None:
            advanced_input_binding.attach_title_row(title_row)
        title_target = getattr(title_row, "_node_title_text_target", None)
        self._surface_composer.mount(
            assembly=surface,
            title_row=title_row,
            title_target=title_target
            if isinstance(title_target, NodeTitleTextTarget)
            else None,
            chevron=chevron,
            metadata=NodeCardSurfaceMetadata(
                cube_alias=alias,
                node_name=node_name,
                node_class_type=node_type,
                variant=node_card_variant.value,
                has_title_controls=has_title_controls,
                has_advanced_input_action=advanced_input_binding is not None,
            ),
            collapsible=(
                has_rows and resolved_behavior.card.collapse_mode != CollapseMode.EXEMPT
            ),
            has_rows=has_rows,
            allow_unbounded_content_height=allow_unbounded_content_height,
        )
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
        log_node_card_build_timing(
            "node_card.built",
            started_at=card_started_at,
            context=log_context,
            visible_group_count=len(visible_keys),
            has_rows=has_rows,
            has_title_controls=has_title_controls,
        )
        build_transaction.commit()
        return wrapper

    def _add_input_row(
        self,
        *,
        label: str,
        widget: QWidget,
        field_behavior: FieldBehavior,
        content_layout: QVBoxLayout,
    ) -> BuiltFieldRow:
        """Add one input row through the shared row builder."""

        return self._body_composer.add_input_row(
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
        field_labels: Mapping[str, str] | None = None,
    ) -> None:
        """Add one grouped multi-column row through the shared row builder."""

        self._body_composer.add_n_column_row(
            fields=fields,
            field_behaviors=field_behaviors,
            content_layout=content_layout,
            node_name=node_name,
            field_labels=field_labels,
        )

    def _gather_visible_keys(
        self,
        *,
        input_keys: list[str],
        resolved_behavior: ResolvedNodeBehavior,
        skip_keys: set[str],
        preferred_field_groups: tuple[tuple[str, ...], ...] = (),
    ) -> list[list[str]]:
        """Delegate visible-field grouping rules to the row-builder collaborator."""

        return self._field_rows.gather_visible_keys(
            input_keys=input_keys,
            field_groups=preferred_field_groups + resolved_behavior.field_groups,
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
            return cast(QWidget, icon)
        spacer = QWidget(widget_parent)
        spacer.setFixedSize(EDITOR_ROW_ICON_SIZE, EDITOR_ROW_ICON_SIZE)
        return spacer


__all__ = [
    "NodeCardBodyComposer",
    "NodeCardBuilder",
    "NodePanelSnapshot",
]
