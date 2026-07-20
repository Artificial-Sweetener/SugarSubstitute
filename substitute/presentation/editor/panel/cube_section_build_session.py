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

"""Build cube-section node cards incrementally for editor projection."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

import weakref
from collections.abc import Mapping
from time import perf_counter
from typing import cast

from PySide6.QtWidgets import QWidget

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_timing,
    log_warning,
    log_warning_exception,
)

from .cube_section_build_plan import (
    NodeCardBuildOutcome,
    NodeCardBuildOutcomeKind,
    empty_card_outcome_kind,
    is_first_usable_card,
    leading_first_usable_node_count,
    node_card_build_outcome,
)
from .node_card.variant import (
    column_span_for_node_card_variant,
    resolve_node_card_variant,
)
from .projection_observability import log_panel_projection_event
from .projection_ports import (
    CubeSectionSessionWidgetProtocol,
    EditorRefreshPanelProtocol,
)
from .rendering.render_transaction import EditorRenderTransaction
from .widgets.masonry_grid_layout import MasonryGridLayout

_LOGGER = get_logger("presentation.editor.panel.cube_section_build_session")


class CubeSectionBuildSession:
    """Build one cube section incrementally while preserving final layout semantics."""

    def __init__(
        self,
        *,
        panel: EditorRefreshPanelProtocol,
        route_key: str,
        cube_state: object,
        cube: dict[str, object],
        behavior_snapshot: object,
        field_specs_by_node: Mapping[str, Mapping[str, ResolvedFieldSpec]],
        node_order: list[str],
        grid_layout: MasonryGridLayout,
        widget: CubeSectionSessionWidgetProtocol,
    ) -> None:
        """Store all immutable context needed to add node cards over time."""

        self._started_at = perf_counter()
        self._panel = panel
        self._route_key = route_key
        self._cube_state = cube_state
        self._cube = cube
        self._behavior_snapshot = behavior_snapshot
        self._field_specs_by_node = field_specs_by_node
        self._node_order = list(node_order)
        self._grid_layout = grid_layout
        self._widget = widget
        self._next_index = 0
        self._built_card_count = 0
        self._skipped_card_count = 0
        self._node_outcomes: list[NodeCardBuildOutcome] = []
        self._finished = False
        self._first_usable_node_count = leading_first_usable_node_count(
            node_order=self._node_order,
            cube=self._cube,
            behavior_snapshot=self._behavior_snapshot,
            cube_alias=self._route_key,
        )
        self._first_usable_reached = self._first_usable_node_count == 0

    @property
    def widget(self) -> CubeSectionSessionWidgetProtocol:
        """Return the cube wrapper receiving incrementally built node cards."""

        return self._widget

    @property
    def is_finished(self) -> bool:
        """Return whether every node in this section has been processed."""

        return self._finished

    @property
    def first_usable_reached(self) -> bool:
        """Return whether leading prompt cards required for first interaction are built."""

        return self._first_usable_reached

    @property
    def deferred_node_count(self) -> int:
        """Return the number of nodes deferred behind first-usable controls."""

        if self._first_usable_node_count == 0:
            return 0
        return len(self._node_order) - self._first_usable_node_count

    @property
    def node_outcomes(self) -> tuple[NodeCardBuildOutcome, ...]:
        """Return the per-node card build outcomes collected so far."""

        return tuple(self._node_outcomes)

    def step(self) -> bool:
        """Build the next node card and return whether the session is complete."""

        step_started_at = perf_counter()
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="cube_section_step_enter",
            cube_alias=self._route_key,
            next_index=self._next_index,
            node_count=len(self._node_order),
            finished=self._finished,
            first_usable_reached=self._first_usable_reached,
            built_card_count=self._built_card_count,
            skipped_card_count=self._skipped_card_count,
        )
        if self._finished:
            return True
        if self._next_index >= len(self._node_order):
            self._finish()
            return True
        node_name = self._node_order[self._next_index]
        self._next_index += 1
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="cube_section_node_step_start",
            cube_alias=self._route_key,
            node_name=node_name,
            node_index=self._next_index,
            node_count=len(self._node_order),
            first_usable_card=is_first_usable_card(
                node_name,
                cube=self._cube,
                behavior_snapshot=self._behavior_snapshot,
                cube_alias=self._route_key,
            ),
        )
        self._build_node(node_name)
        if not self._first_usable_reached and (
            self._next_index >= self._first_usable_node_count
        ):
            self._first_usable_reached = True
            log_panel_projection_event(
                "hidden_build.first_usable",
                cube_alias=self._route_key,
                built_card_count=self._built_card_count,
                skipped_card_count=self._skipped_card_count,
                deferred_node_count=len(self._node_order) - self._next_index,
                projection_mode="live",
            )
            log_timing(
                _LOGGER,
                "Reached first usable cube-section card set",
                started_at=self._started_at,
                cube_alias=self._route_key,
                built_card_count=self._built_card_count,
                skipped_card_count=self._skipped_card_count,
                deferred_node_count=len(self._node_order) - self._next_index,
                level="debug",
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="cube_section_first_usable_reached",
                cube_alias=self._route_key,
                node_index=self._next_index,
                node_count=len(self._node_order),
                built_card_count=self._built_card_count,
                skipped_card_count=self._skipped_card_count,
                deferred_node_count=len(self._node_order) - self._next_index,
            )
        log_timing(
            _LOGGER,
            "Built cube-section node card step",
            started_at=step_started_at,
            level="debug",
            cube_alias=self._route_key,
            node_name=node_name,
            node_index=self._next_index,
            node_count=len(self._node_order),
            finished=self._next_index >= len(self._node_order),
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="cube_section_node_step_end",
            cube_alias=self._route_key,
            node_name=node_name,
            node_index=self._next_index,
            node_count=len(self._node_order),
            finished=self._next_index >= len(self._node_order),
            built_card_count=self._built_card_count,
            skipped_card_count=self._skipped_card_count,
            last_outcome=(
                f"{self._node_outcomes[-1].node_name}:{self._node_outcomes[-1].kind}"
                if self._node_outcomes
                else ""
            ),
        )
        if self._next_index >= len(self._node_order):
            self._finish()
        return self._finished

    def finish(self) -> None:
        """Build all remaining cards synchronously for legacy callers."""

        finish_started_at = perf_counter()
        while not self.step():
            continue
        log_timing(
            _LOGGER,
            "Finished remaining cube-section cards synchronously",
            started_at=finish_started_at,
            cube_alias=self._route_key,
            node_count=len(self._node_order),
            level="debug",
        )

    def _record_node_outcome(
        self,
        *,
        node_name: str,
        node_class_type: str,
        kind: NodeCardBuildOutcomeKind,
        field_spec_count: int,
        message: str = "",
    ) -> None:
        """Record how one node was handled during section projection."""

        self._node_outcomes.append(
            node_card_build_outcome(
                node_name=node_name,
                node_class_type=node_class_type,
                kind=kind,
                field_spec_count=field_spec_count,
                message=message,
            )
        )

    def _build_node(self, node_name: str) -> None:
        """Build one node card into the grid when behavior says it is visible."""

        node_started_at = perf_counter()
        nodes = self._cube.get("nodes", {})
        if not isinstance(nodes, dict) or node_name not in nodes:
            self._skipped_card_count += 1
            self._record_node_outcome(
                node_name=node_name,
                node_class_type="",
                kind="missing_behavior",
                field_spec_count=0,
                message=app_text("node missing from cube buffer"),
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="cube_section_node_skipped",
                cube_alias=self._route_key,
                node_name=node_name,
                reason="node_missing_from_cube_buffer",
                built_card_count=self._built_card_count,
                skipped_card_count=self._skipped_card_count,
            )
            return
        node_data = nodes[node_name]
        if not isinstance(node_data, dict):
            self._skipped_card_count += 1
            self._record_node_outcome(
                node_name=node_name,
                node_class_type="",
                kind="missing_behavior",
                field_spec_count=0,
                message=app_text("node payload is not a mapping"),
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="cube_section_node_skipped",
                cube_alias=self._route_key,
                node_name=node_name,
                reason="node_payload_not_mapping",
                built_card_count=self._built_card_count,
                skipped_card_count=self._skipped_card_count,
            )
            return
        inputs = node_data.get("inputs", {})
        if not isinstance(inputs, dict):
            inputs = {}
        node_type = node_data.get("class_type", "")
        resolved_nodes = getattr(
            self._behavior_snapshot,
            "resolved_nodes_by_alias",
            {},
        )
        resolved_behavior = resolved_nodes.get(self._route_key, {}).get(node_name)
        node_field_specs = self._field_specs_by_node.get(node_name, {})
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="cube_section_node_build_begin",
            cube_alias=self._route_key,
            node_name=node_name,
            node_class_type=str(node_type),
            input_count=len(inputs),
            field_spec_count=len(node_field_specs),
            resolved_behavior_present=resolved_behavior is not None,
        )
        if resolved_behavior is None:
            self._skipped_card_count += 1
            self._record_node_outcome(
                node_name=node_name,
                node_class_type=str(node_type),
                kind="missing_behavior",
                field_spec_count=len(node_field_specs),
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="cube_section_node_skipped",
                cube_alias=self._route_key,
                node_name=node_name,
                node_class_type=str(node_type),
                reason="missing_behavior",
                field_spec_count=len(node_field_specs),
                built_card_count=self._built_card_count,
                skipped_card_count=self._skipped_card_count,
            )
            return

        display_decision = (
            getattr(
                self._behavior_snapshot,
                "card_decisions_by_alias",
                {},
            )
            .get(self._route_key, {})
            .get(node_name)
        )
        is_subgraph_wrapper_card = self._is_subgraph_wrapper_card(node_field_specs)
        if is_subgraph_wrapper_card:
            log_debug(
                _LOGGER,
                "Building subgraph wrapper cube-section card",
                cube_alias=self._route_key,
                node_name=node_name,
                node_class_type=str(node_type),
                field_spec_keys=",".join(node_field_specs.keys()),
                decision_visible=getattr(display_decision, "visible", None),
                decision_enabled=getattr(display_decision, "enabled", None),
                decision_reason=getattr(display_decision, "reason", None),
                show_enabled_switch=getattr(
                    display_decision,
                    "show_enabled_switch",
                    None,
                ),
            )
        try:
            node_card = self._panel.build_node_card(
                node_name,
                inputs,
                str(node_type),
                node_field_specs,
                cast(dict[str, object], self._cube_state),
                resolved_behavior,
                display_decision,
                alias=self._route_key,
                parent=self._widget,
            )
        except (RuntimeError, TypeError, ValueError) as error:
            self._skipped_card_count += 1
            self._record_node_outcome(
                node_name=node_name,
                node_class_type=str(node_type),
                kind="build_error",
                field_spec_count=len(node_field_specs),
                message=repr(error),
            )
            log_warning_exception(
                _LOGGER,
                "Skipped cube-section node card after build failure",
                error=error,
                cube_alias=self._route_key,
                node_name=node_name,
                node_class_type=str(node_type),
                field_spec_count=len(node_field_specs),
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="cube_section_node_build_error",
                cube_alias=self._route_key,
                node_name=node_name,
                node_class_type=str(node_type),
                field_spec_count=len(node_field_specs),
                error_type=type(error).__name__,
                built_card_count=self._built_card_count,
                skipped_card_count=self._skipped_card_count,
            )
            return
        if node_card is None:
            self._skipped_card_count += 1
            outcome_kind = empty_card_outcome_kind(
                inputs=inputs,
                field_specs=node_field_specs,
                display_decision=display_decision,
            )
            self._record_node_outcome(
                node_name=node_name,
                node_class_type=str(node_type),
                kind=outcome_kind,
                field_spec_count=len(node_field_specs),
            )
            if is_subgraph_wrapper_card:
                log_debug(
                    _LOGGER,
                    "Skipped subgraph wrapper cube-section card",
                    cube_alias=self._route_key,
                    node_name=node_name,
                    node_class_type=str(node_type),
                    field_spec_count=len(node_field_specs),
                    built_card_count=self._built_card_count,
                    skipped_card_count=self._skipped_card_count,
                )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="cube_section_node_skipped",
                cube_alias=self._route_key,
                node_name=node_name,
                node_class_type=str(node_type),
                reason=outcome_kind,
                field_spec_count=len(node_field_specs),
                decision_visible=getattr(display_decision, "visible", None),
                decision_enabled=getattr(display_decision, "enabled", None),
                built_card_count=self._built_card_count,
                skipped_card_count=self._skipped_card_count,
            )
            return
        self._built_card_count += 1
        self._record_node_outcome(
            node_name=node_name,
            node_class_type=str(node_type),
            kind="built",
            field_spec_count=len(node_field_specs),
        )
        node_card_widget = cast(QWidget, node_card)
        setattr(node_card_widget, "_current_cube_alias", self._route_key)
        self._panel.register_card_wrapper(
            self._route_key,
            node_name,
            node_card_widget,
        )
        try:
            panel = self._panel
            cube_alias = self._route_key
            current_node_name = node_name
            wrapper_ref = weakref.ref(node_card_widget)

            def cleanup_card_wrapper(*_args: object) -> None:
                """Remove the wrapper only if it still owns the registry entry."""

                current_node_card = wrapper_ref()
                if current_node_card is None:
                    return
                panel.remove_card_wrapper_if_current(
                    cube_alias,
                    current_node_name,
                    current_node_card,
                )

            node_card_widget.destroyed.connect(cleanup_card_wrapper)
        except (AttributeError, RuntimeError, TypeError) as error:
            log_warning(
                _LOGGER,
                "Failed to connect cube-section card cleanup",
                cube_alias=self._route_key,
                node_name=node_name,
                error_type=type(error).__name__,
            )

        node_card_variant = resolve_node_card_variant(resolved_behavior)
        span = column_span_for_node_card_variant(node_card_variant)
        node_card_widget.setProperty("column_span", span)
        node_card_widget.setProperty("node_card_variant", node_card_variant.value)
        self._grid_layout.addWidget(node_card_widget)
        if isinstance(self._panel, QWidget):
            with EditorRenderTransaction(self._panel) as transaction:
                transaction.attach_node_card(node_card_widget)
        self._widget.defer_update_cube_height()
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="cube_section_node_built",
            cube_alias=self._route_key,
            node_name=node_name,
            node_class_type=str(node_type),
            field_spec_count=len(node_field_specs),
            column_span=span,
            node_card_type=type(node_card_widget).__name__,
            built_card_count=self._built_card_count,
            skipped_card_count=self._skipped_card_count,
        )
        if is_subgraph_wrapper_card:
            log_debug(
                _LOGGER,
                "Built subgraph wrapper cube-section card",
                cube_alias=self._route_key,
                node_name=node_name,
                node_class_type=str(node_type),
                field_spec_count=len(node_field_specs),
                built_card_count=self._built_card_count,
                skipped_card_count=self._skipped_card_count,
            )
        log_timing(
            _LOGGER,
            "Built cube-section node card",
            started_at=node_started_at,
            level="debug",
            cube_alias=self._route_key,
            node_name=node_name,
            node_class_type=str(node_type),
            input_count=len(inputs),
            field_spec_count=len(node_field_specs),
            built_card_count=self._built_card_count,
            skipped_card_count=self._skipped_card_count,
        )

    @staticmethod
    def _is_subgraph_wrapper_card(
        field_specs: Mapping[str, Mapping[str, object] | ResolvedFieldSpec],
    ) -> bool:
        """Return whether the field specs belong to a subgraph wrapper card."""

        for field_spec in field_specs.values():
            meta_info = getattr(field_spec, "meta_info", None)
            if (
                isinstance(meta_info, Mapping)
                and meta_info.get("subgraph_wrapper") is True
            ):
                return True
        return False

    def _finish(self) -> None:
        """Mark this build session complete and emit final sizing refreshes."""

        self._finished = True
        self._widget.defer_update_cube_height()
        defer_string_width_sync = getattr(
            self._widget,
            "defer_string_line_edit_width_group_sync",
            None,
        )
        if callable(defer_string_width_sync):
            defer_string_width_sync()
        elapsed_ms = (perf_counter() - self._started_at) * 1000.0
        log_panel_projection_event(
            "hidden_build.session_complete",
            cube_alias=self._route_key,
            built_card_count=self._built_card_count,
            skipped_card_count=self._skipped_card_count,
            node_count=len(self._node_order),
            elapsed_ms=f"{elapsed_ms:.3f}",
            projection_mode="live",
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="cube_section_session_complete",
            cube_alias=self._route_key,
            built_card_count=self._built_card_count,
            skipped_card_count=self._skipped_card_count,
            node_count=len(self._node_order),
            elapsed_ms=f"{elapsed_ms:.3f}",
            node_outcomes=tuple(
                f"{outcome.node_name}:{outcome.kind}" for outcome in self._node_outcomes
            ),
        )
        log_timing(
            _LOGGER,
            "Completed cube-section node card build",
            started_at=self._started_at,
            cube_alias=self._route_key,
            built_card_count=self._built_card_count,
            skipped_card_count=self._skipped_card_count,
            node_count=len(self._node_order),
            node_outcomes=tuple(
                f"{outcome.node_name}:{outcome.kind}" for outcome in self._node_outcomes
            ),
            level="debug",
        )
