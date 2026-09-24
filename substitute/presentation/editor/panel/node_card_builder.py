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
from typing import Any

from PySide6.QtWidgets import QWidget


from substitute.application.node_behavior import (
    CollapseMode,
    NodeDisplayDecision,
    ResolvedFieldSpec,
    ResolvedNodeBehavior,
)
from .node_card.advanced_input_binding import AdvancedInputCardBinding
from .node_card.body_composer import NodeCardBodyComposer
from .node_card.body_contribution import NodeCardBodyContributor
from .node_card.body_realizer import NodeCardBodyRealizer
from .node_card.build_observability import (
    NodeCardBuildLogContext,
    log_node_card_build_timing,
)
from .node_card.field_realizer import NodeCardFieldRealizer
from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalogSource,
)
from .node_card.panel_snapshot import (
    capture_node_panel_snapshot,
)
from .node_card.row_icon_factory import NodeCardRowIconFactory
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
        field_realizer = NodeCardFieldRealizer(
            panel=panel,
            services=services,
            model_choice_snapshot_controller=model_choice_snapshot_controller,
            prompt_segment_preset_source=prompt_segment_preset_source,
        )
        row_icons = NodeCardRowIconFactory(panel=panel)
        self._field_rows = FieldRowBuilder(
            panel=panel,
            icon_builder=row_icons.build,
            icon_resolver=row_icons.resolve,
            dimension_preset_source=dimension_preset_source,
        )
        self._body_composer = NodeCardBodyComposer(
            panel=panel,
            field_rows=self._field_rows,
        )
        self._body_realizer = NodeCardBodyRealizer(
            panel=panel,
            field_realizer=field_realizer,
            field_rows=self._field_rows,
            body_composer=self._body_composer,
            body_contributors=body_contributors,
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
        allow_unbounded_content_height = (
            resolved_behavior.card.collapse_mode == CollapseMode.EXEMPT
        )
        node_card_variant = resolve_node_card_variant(resolved_behavior)
        try:
            body_result = self._body_realizer.realize(
                node_name=node_name,
                node_type=node_type,
                inputs=inputs,
                field_specs=field_specs,
                resolved_behavior=resolved_behavior,
                cube_state=cube_state,
                alias=alias,
                content_body=content_body,
                content_layout=content_layout,
                allow_unbounded_content_height=allow_unbounded_content_height,
                build_transaction=build_transaction,
                prompt_field_inputs=prompt_field_inputs,
                node_presentation=node_presentation,
                presentation_binding=presentation_binding,
                log_context=log_context,
                show_enabled_switch=bool(
                    display_decision is not None
                    and display_decision.show_enabled_switch
                ),
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
        is_subgraph_wrapper_card = body_result.is_subgraph_wrapper
        visible_keys = body_result.visible_groups
        field_action_contributions = body_result.action_contributions
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


__all__ = ["NodeCardBuilder"]
