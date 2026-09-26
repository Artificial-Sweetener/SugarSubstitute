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

"""Realize and bind one node-card field from its resolved specification."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.domain.localization import (
    FieldPresentation as LocalizedFieldPresentation,
)
from substitute.presentation.editor.panel.factories import widget_wiring
from substitute.presentation.editor.panel.factories.field_build_outcome import (
    EditorFieldBuildKind,
)
from substitute.presentation.editor.panel.factories.field_pipeline import (
    LAYOUT_HANDLED,
)
from substitute.presentation.editor.panel.field_state_controller import (
    EditorPanelFieldStateController,
)
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshotController,
)
from substitute.presentation.editor.panel.node_card_build_transaction import (
    NodeCardBuildTransaction,
)
from substitute.presentation.editor.panel.node_card.field_factory_adapter import (
    NodeCardFieldFactoryAdapter,
)
from substitute.presentation.editor.panel.prompt.field_inputs import (
    NodeCardPromptFieldInputs,
)
from substitute.presentation.editor.panel.projection_observability import (
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)
from substitute.presentation.editor.panel.service_bundle import EditorPanelServiceBundle
from substitute.presentation.editor.panel.widgets.field_relayout import (
    bind_field_widget_card_relayout,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetSource,
)
from substitute.presentation.editor.utils import sanitation
from substitute.shared.logging.logger import (
    get_logger,
    log_warning,
    log_warning_exception,
)

_LOGGER = get_logger("presentation.editor.panel.node_card.field_realizer")


@dataclass(frozen=True, slots=True)
class _FieldLogContext:
    """Carry prompt-safe field realization diagnostic fields."""

    cube_alias: str
    node_name: str
    node_class: str
    field_key: str
    field_type: str
    presentation: str


def _log_field_timing(
    event: str,
    *,
    started_at: float,
    context: _FieldLogContext,
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


class NodeCardFieldRealizer:
    """Build, annotate, bind, and stage node-card field widgets."""

    def __init__(
        self,
        *,
        panel: Any,
        services: EditorPanelServiceBundle,
        model_choice_snapshot_controller: PanelModelChoiceSnapshotController | None,
        prompt_segment_preset_source: PromptSegmentPresetSource | None,
    ) -> None:
        """Capture field factory, prompt runtime, and panel binding collaborators."""

        self._panel = panel
        self._factory = NodeCardFieldFactoryAdapter(
            panel=panel,
            services=services,
            model_choice_snapshot_controller=model_choice_snapshot_controller,
            prompt_segment_preset_source=prompt_segment_preset_source,
        )

    def realize(
        self,
        *,
        node_name: str,
        field_spec: ResolvedFieldSpec,
        content_body: QWidget | None,
        content_layout: QVBoxLayout | None,
        allow_unbounded_content_height: bool,
        cube_state: Any,
        alias: str | None,
        field_presentation: LocalizedFieldPresentation,
        build_transaction: NodeCardBuildTransaction,
        prompt_field_inputs: Mapping[str, NodeCardPromptFieldInputs] | None = None,
    ) -> Any:
        """Build one field and attach every required runtime integration."""

        field_started_at = panel_projection_observability_started_at()
        key = field_spec.field_key
        extended_meta = dict(field_spec.meta_info)
        extended_meta["cube_alias"] = alias
        if field_presentation.tooltip is not None:
            extended_meta["tooltip"] = field_presentation.tooltip
        cube_buffer = self._cube_buffer(cube_state)
        node_data = cube_buffer.get("nodes", {}).get(node_name)
        if isinstance(node_data, dict):
            extended_meta["node_data"] = node_data
        factory_started_at = panel_projection_observability_started_at()
        log_context = _FieldLogContext(
            cube_alias=alias or "",
            node_name=node_name,
            node_class=field_spec.class_type,
            field_key=key,
            field_type=field_spec.field_type or "",
            presentation=field_spec.field_behavior.presentation.value,
        )
        outcome = self._factory.build(
            field_spec=field_spec,
            extended_meta=extended_meta,
            prompt_field_inputs=prompt_field_inputs,
        )
        _log_field_timing(
            "node_card.field_factory",
            started_at=factory_started_at,
            context=log_context,
            result_type=outcome.kind.value,
        )
        if outcome.kind is EditorFieldBuildKind.ERROR:
            error = outcome.error
            if error is not None:
                log_warning_exception(
                    _LOGGER,
                    "Skipped editor field after factory failure",
                    error=error,
                    cube_alias=alias or "",
                    node_name=node_name,
                    node_class=field_spec.class_type,
                    field_key=key,
                    field_type=field_spec.field_type or "",
                    value_source=field_spec.value_source.value,
                )
            return None
        if outcome.kind is EditorFieldBuildKind.LAYOUT_HANDLED:
            return LAYOUT_HANDLED
        if not outcome.rendered:
            if outcome.kind is EditorFieldBuildKind.UNSUPPORTED:
                log_warning(
                    _LOGGER,
                    "Skipped unsupported editor field",
                    cube_alias=alias or "",
                    node_name=node_name,
                    node_class=field_spec.class_type,
                    field_key=key,
                    field_type=field_spec.field_type or "",
                    reason=outcome.reason,
                )
            return None
        result = outcome.surface
        if result is None:
            return None
        widget = cast(Any, result[0] if isinstance(result, tuple) else result)
        metadata = self._field_metadata(
            alias=alias,
            node_name=node_name,
            field_spec=field_spec,
            field_presentation=field_presentation,
            extended_meta=extended_meta,
        )
        widget.setProperty(
            "input_metadata",
            sanitation.deep_sanitize_for_qt(metadata),
        )
        configure_wheel_intent = getattr(
            self._panel,
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
            widget.setProperty("column_span", field_spec.field_behavior.column_span)
        wiring_started_at = panel_projection_observability_started_at()
        self._wire_widget(widget, cube_state, metadata)
        _log_field_timing(
            "node_card.field_wired",
            started_at=wiring_started_at,
            context=log_context,
            widget_type=widget.__class__.__name__,
        )
        if alias is not None:
            build_transaction.stage(field_key=key, widget=widget)
        widget_wiring.bind_picker_signals(
            widget,
            self._panel,
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
        _log_field_timing(
            "node_card.field_prepared",
            started_at=field_started_at,
            context=log_context,
            widget_type=widget.__class__.__name__,
        )
        return widget

    def _wire_widget(
        self,
        widget: Any,
        cube_state: Any,
        metadata: dict[str, Any],
    ) -> None:
        """Bind field state and prompt-layout notifications through their owner."""

        layout_changed = getattr(self._panel, "promptEditorLayoutChanged", None)
        emit_layout_changed = getattr(layout_changed, "emit", None)

        def emit_prompt_layout_changed() -> None:
            """Emit prompt layout change when a prompt editor height changes."""

            if callable(emit_layout_changed):
                emit_layout_changed()

        controller = getattr(self._panel, "_field_state_controller", None)
        if not isinstance(controller, EditorPanelFieldStateController):
            controller = EditorPanelFieldStateController(self._panel)
            setattr(self._panel, "_field_state_controller", controller)
        controller.bind_node_widget_state(
            widget,
            cube_state,
            metadata,
            manual_prompt_height_changed=emit_prompt_layout_changed
            if callable(emit_layout_changed)
            else None,
        )

    @staticmethod
    def _cube_buffer(cube_state: Any) -> dict[str, Any]:
        """Return the mutable cube buffer when present."""

        buffer = getattr(cube_state, "buffer", None)
        return buffer if isinstance(buffer, dict) else {}

    @staticmethod
    def _field_metadata(
        *,
        alias: str | None,
        node_name: str,
        field_spec: ResolvedFieldSpec,
        field_presentation: LocalizedFieldPresentation,
        extended_meta: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the authoritative runtime metadata for one realized field."""

        return {
            "cube_alias": alias,
            "node_name": node_name,
            "key": field_spec.field_key,
            "type": field_spec.field_type,
            "meta_info": extended_meta,
            "field_info": field_spec.field_info,
            "constraints": dict(field_spec.constraints),
            "node_type": field_spec.class_type,
            "tooltip": field_presentation.tooltip,
            "resolved_value": field_spec.value,
            "value_source": field_spec.value_source.value,
        }


__all__ = ["NodeCardFieldRealizer"]
