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

"""Route one eligible node-card field through the focused realizer."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.application.node_behavior import ResolvedFieldSpec, ResolvedNodeBehavior
from substitute.domain.localization import NodePresentation
from substitute.presentation.editor.panel.factories.field_pipeline import LAYOUT_HANDLED
from substitute.presentation.editor.panel.node_card_build_transaction import (
    NodeCardBuildTransaction,
)
from substitute.presentation.editor.panel.prompt.field_inputs import (
    NodeCardPromptFieldInputs,
)

from .build_observability import log_wrapper_field_trace
from .field_realizer import NodeCardFieldRealizer


class NodeCardBodyFieldRouter:
    """Apply connection and behavior policy before realizing one field widget."""

    def __init__(self, *, panel: Any, field_realizer: NodeCardFieldRealizer) -> None:
        """Capture the panel policy surface and the authoritative realizer."""

        self._panel = panel
        self._field_realizer = field_realizer

    def realize(
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
        is_subgraph_wrapper: bool,
    ) -> QWidget | None:
        """Return a realized widget or skip the ineligible/handled field."""

        field_spec = field_specs[key]
        if self._panel.is_connection(inputs.get(key)):
            self._trace(
                is_subgraph_wrapper,
                alias,
                node_name,
                key,
                "skip_connection",
                field_spec,
            )
            return None
        if resolved_behavior.fields.get(key) is None:
            self._trace(
                is_subgraph_wrapper,
                alias,
                node_name,
                key,
                "skip_missing_behavior",
                field_spec,
            )
            return None
        self._trace(
            is_subgraph_wrapper,
            alias,
            node_name,
            key,
            "field_attempt",
            field_spec,
        )
        field = self._field_realizer.realize(
            node_name=node_name,
            field_spec=field_spec,
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
            self._trace(
                is_subgraph_wrapper,
                alias,
                node_name,
                key,
                "layout_handled" if field is LAYOUT_HANDLED else "factory_none",
                field_spec,
            )
            return None
        widget = cast(QWidget, field)
        log_wrapper_field_trace(
            enabled=is_subgraph_wrapper,
            alias=alias,
            node_name=node_name,
            key=key,
            action="widget_built",
            field_spec=field_spec,
            widget_type=widget.__class__.__name__,
        )
        return widget

    @staticmethod
    def _trace(
        enabled: bool,
        alias: str | None,
        node_name: str,
        key: str,
        action: str,
        field_spec: ResolvedFieldSpec,
    ) -> None:
        """Report one wrapper-field realization decision."""

        log_wrapper_field_trace(
            enabled=enabled,
            alias=alias,
            node_name=node_name,
            key=key,
            action=action,
            field_spec=field_spec,
        )


__all__ = ["NodeCardBodyFieldRouter"]
