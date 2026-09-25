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

"""Realize grouped node-card fields and collect their title actions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.application.node_behavior import (
    FieldBehavior,
    ResolvedFieldSpec,
    ResolvedNodeBehavior,
)
from substitute.domain.localization import NodePresentation
from substitute.presentation.editor.field_actions import FieldActionContribution
from substitute.presentation.editor.panel.node_card_build_transaction import (
    NodeCardBuildTransaction,
)
from substitute.presentation.editor.panel.node_presentation_binding import (
    NodeCardPresentationBinding,
)
from substitute.presentation.editor.panel.prompt.field_inputs import (
    NodeCardPromptFieldInputs,
)
from substitute.presentation.editor.panel.projection_observability import (
    panel_projection_observability_started_at,
)
from substitute.presentation.editor.panel.widgets.field_row import FieldRowBuilder

from .body_composer import NodeCardBodyComposer
from .body_field_router import NodeCardBodyFieldRouter
from .body_contribution import (
    NodeCardBodyContribution,
    NodeCardBodyContributionContext,
    NodeCardBodyContributor,
)
from .build_observability import (
    NodeCardBuildLogContext,
    log_node_card_build_timing,
    log_subgraph_card_build_started,
)
from .field_realizer import NodeCardFieldRealizer


@dataclass(frozen=True, slots=True)
class NodeCardBodyResult:
    """Describe realized body groups and the actions contributed by their rows."""

    action_contributions: tuple[FieldActionContribution, ...]
    visible_groups: tuple[tuple[str, ...], ...]
    is_subgraph_wrapper: bool


class NodeCardBodyRealizer:
    """Own visible field grouping, realization, and row contribution assembly."""

    def __init__(
        self,
        *,
        panel: Any,
        field_realizer: NodeCardFieldRealizer,
        field_rows: FieldRowBuilder,
        body_composer: NodeCardBodyComposer,
        body_contributors: tuple[NodeCardBodyContributor, ...],
    ) -> None:
        """Capture field and row collaborators used for each card body."""

        self._panel = panel
        self._field_router = NodeCardBodyFieldRouter(
            panel=panel,
            field_realizer=field_realizer,
        )
        self._field_rows = field_rows
        self._body_composer = body_composer
        self._body_contributors = body_contributors

    def realize(
        self,
        *,
        node_name: str,
        node_type: str,
        inputs: Mapping[str, Any],
        field_specs: Mapping[str, ResolvedFieldSpec],
        resolved_behavior: ResolvedNodeBehavior,
        cube_state: Any,
        alias: str | None,
        content_body: QWidget,
        content_layout: QVBoxLayout,
        allow_unbounded_content_height: bool,
        build_transaction: NodeCardBuildTransaction,
        prompt_field_inputs: Mapping[str, NodeCardPromptFieldInputs] | None,
        node_presentation: NodePresentation,
        presentation_binding: NodeCardPresentationBinding,
        log_context: NodeCardBuildLogContext,
        show_enabled_switch: bool,
    ) -> NodeCardBodyResult:
        """Realize every visible field group and return title action contributions."""

        contributions = self._body_contributions(
            alias=alias,
            node_name=node_name,
            node_type=node_type,
            inputs=inputs,
            cube_state=cube_state,
        )
        visible_groups = tuple(
            tuple(group)
            for group in self._field_rows.gather_visible_keys(
                input_keys=list(field_specs),
                field_groups=(
                    tuple(contribution.field_keys for contribution in contributions)
                    + resolved_behavior.field_groups
                ),
                skip_keys=set(),
            )
        )
        is_subgraph_wrapper = self._is_subgraph_wrapper(field_specs)
        if is_subgraph_wrapper:
            log_subgraph_card_build_started(
                alias=alias,
                node_name=node_name,
                node_type=node_type,
                field_spec_keys=tuple(field_specs),
                visible_groups=visible_groups,
                show_enabled_switch=show_enabled_switch,
            )
        fields_started_at = panel_projection_observability_started_at()
        actions: list[FieldActionContribution] = []
        for group in visible_groups:
            if len(group) > 1:
                actions.extend(
                    self._realize_group(
                        keys=group,
                        contributions=contributions,
                        node_name=node_name,
                        inputs=inputs,
                        field_specs=field_specs,
                        resolved_behavior=resolved_behavior,
                        cube_state=cube_state,
                        alias=alias,
                        content_body=content_body,
                        content_layout=content_layout,
                        allow_unbounded_content_height=(allow_unbounded_content_height),
                        build_transaction=build_transaction,
                        prompt_field_inputs=prompt_field_inputs,
                        node_presentation=node_presentation,
                        presentation_binding=presentation_binding,
                        is_subgraph_wrapper=is_subgraph_wrapper,
                    )
                )
                continue
            actions.extend(
                self._realize_single(
                    key=group[0],
                    node_name=node_name,
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
                    is_subgraph_wrapper=is_subgraph_wrapper,
                )
            )
        log_node_card_build_timing(
            "node_card.build_fields",
            started_at=fields_started_at,
            context=log_context,
            visible_group_count=len(visible_groups),
        )
        return NodeCardBodyResult(
            action_contributions=tuple(actions),
            visible_groups=visible_groups,
            is_subgraph_wrapper=is_subgraph_wrapper,
        )

    def _realize_group(
        self,
        *,
        keys: tuple[str, ...],
        contributions: tuple[NodeCardBodyContribution, ...],
        node_name: str,
        inputs: Mapping[str, Any],
        field_specs: Mapping[str, ResolvedFieldSpec],
        resolved_behavior: ResolvedNodeBehavior,
        cube_state: Any,
        alias: str | None,
        content_body: QWidget,
        content_layout: QVBoxLayout,
        allow_unbounded_content_height: bool,
        build_transaction: NodeCardBuildTransaction,
        prompt_field_inputs: Mapping[str, NodeCardPromptFieldInputs] | None,
        node_presentation: NodePresentation,
        presentation_binding: NodeCardPresentationBinding,
        is_subgraph_wrapper: bool,
    ) -> tuple[FieldActionContribution, ...]:
        """Realize one multi-column group and append its composed row."""

        widgets: list[tuple[str, QWidget]] = []
        field_behaviors: dict[str, FieldBehavior] = {}
        for key in keys:
            field = self._field_router.realize(
                key=key,
                node_name=node_name,
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
                is_subgraph_wrapper=is_subgraph_wrapper,
            )
            if field is None:
                continue
            widgets.append((key, field))
            field_behaviors[key] = resolved_behavior.fields[key]
        if not widgets:
            return ()
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
                key: node_presentation.fields[key].label for key, _widget in widgets
            },
            contribution=contribution,
        )
        presentation_binding.add_field_targets(built_row.text_targets)
        return built_row.action_contributions

    def _realize_single(
        self,
        *,
        key: str,
        node_name: str,
        inputs: Mapping[str, Any],
        field_specs: Mapping[str, ResolvedFieldSpec],
        resolved_behavior: ResolvedNodeBehavior,
        cube_state: Any,
        alias: str | None,
        content_body: QWidget,
        content_layout: QVBoxLayout,
        allow_unbounded_content_height: bool,
        build_transaction: NodeCardBuildTransaction,
        prompt_field_inputs: Mapping[str, NodeCardPromptFieldInputs] | None,
        node_presentation: NodePresentation,
        presentation_binding: NodeCardPresentationBinding,
        is_subgraph_wrapper: bool,
    ) -> tuple[FieldActionContribution, ...]:
        """Realize one full-width field and append its composed row."""

        field = self._field_router.realize(
            key=key,
            node_name=node_name,
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
            is_subgraph_wrapper=is_subgraph_wrapper,
        )
        if field is None:
            return ()
        built_row = self._body_composer.add_input_row(
            label=node_presentation.fields[key].label,
            widget=field,
            field_behavior=resolved_behavior.fields[key],
            content_layout=content_layout,
        )
        presentation_binding.add_field_targets(built_row.text_targets)
        return built_row.action_contributions

    def _body_contributions(
        self,
        *,
        alias: str | None,
        node_name: str,
        node_type: str,
        inputs: Mapping[str, Any],
        cube_state: Any,
    ) -> tuple[NodeCardBodyContribution, ...]:
        """Collect optional synthetic row contributions for this node."""

        raw_graph = getattr(cube_state, "buffer", None)
        graph = raw_graph if isinstance(raw_graph, Mapping) else {}
        context = NodeCardBodyContributionContext(
            section_key=alias or "",
            node_name=node_name,
            node_type=node_type,
            inputs=inputs,
            graph=graph,
        )
        return tuple(
            contribution
            for contributor in self._body_contributors
            if (contribution := contributor.build(context)) is not None
        )

    @staticmethod
    def _is_subgraph_wrapper(
        field_specs: Mapping[str, ResolvedFieldSpec],
    ) -> bool:
        """Return whether the fields belong to a subgraph-wrapper card."""

        return any(
            field_spec.meta_info.get("subgraph_wrapper") is True
            for field_spec in field_specs.values()
        )


__all__ = ["NodeCardBodyRealizer", "NodeCardBodyResult"]
