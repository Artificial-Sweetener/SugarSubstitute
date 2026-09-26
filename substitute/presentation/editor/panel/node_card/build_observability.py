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

"""Report prompt-safe node-card construction timing and field traces."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.presentation.editor.panel.projection_observability import (
    log_panel_projection_timing,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.editor.panel.node_card.build_observability")


@dataclass(frozen=True, slots=True)
class NodeCardBuildLogContext:
    """Carry prompt-safe node-card build diagnostic fields."""

    cube_alias: str
    node_name: str
    node_class: str
    field_spec_count: int


def log_node_card_build_timing(
    event: str,
    *,
    started_at: float,
    context: NodeCardBuildLogContext,
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


def log_wrapper_field_trace(
    *,
    enabled: bool,
    alias: str | None,
    node_name: str,
    key: str,
    action: str,
    field_spec: ResolvedFieldSpec | None,
    widget_type: str = "",
) -> None:
    """Log subgraph-wrapper field decisions used for projection diagnosis."""

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
        raw_value_present=(
            field_spec.raw_value is not None if field_spec is not None else ""
        ),
        default="default" in field_spec.meta_info if field_spec is not None else "",
        value_source=(field_spec.value_source.value if field_spec is not None else ""),
    )


def log_subgraph_card_build_started(
    *,
    alias: str | None,
    node_name: str,
    node_type: str,
    field_spec_keys: tuple[str, ...],
    visible_groups: tuple[tuple[str, ...], ...],
    show_enabled_switch: bool,
) -> None:
    """Report the resolved field projection for a subgraph-wrapper card."""

    log_debug(
        _LOGGER,
        "Building subgraph wrapper node card",
        cube_alias=alias or "",
        node_name=node_name,
        node_class=node_type,
        field_spec_keys=",".join(field_spec_keys),
        visible_groups=";".join(",".join(group) for group in visible_groups),
        title_switch=show_enabled_switch,
    )


__all__ = [
    "NodeCardBuildLogContext",
    "log_node_card_build_timing",
    "log_subgraph_card_build_started",
    "log_wrapper_field_trace",
]
