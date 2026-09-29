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

"""Adapt node-card field specifications to the shared widget factory."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.presentation.editor.panel.execution_factories import (
    PromptEditorTaskExecutorFactory,
)
from substitute.presentation.editor.panel.factories.field_build_outcome import (
    EditorFieldBuildOutcome,
)
from substitute.presentation.editor.panel.factories.field_build_resolver import (
    resolve_editor_field_build,
)
from substitute.presentation.editor.panel.factories.field_pipeline import (
    LAYOUT_HANDLED,
    build_widget_for_field_spec,
)
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshotController,
)
from substitute.presentation.editor.panel.prompt.field_build_arguments import (
    prompt_field_build_arguments,
)
from substitute.presentation.editor.panel.prompt.field_inputs import (
    NodeCardPromptFieldInputs,
)
from substitute.presentation.editor.panel.service_bundle import EditorPanelServiceBundle
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetSource,
)


class NodeCardFieldFactoryAdapter:
    """Supply explicit editor dependencies to the shared field factory."""

    def __init__(
        self,
        *,
        panel: Any,
        services: EditorPanelServiceBundle,
        model_choice_snapshot_controller: PanelModelChoiceSnapshotController | None,
        prompt_segment_preset_source: PromptSegmentPresetSource | None,
    ) -> None:
        """Capture dependencies needed only while invoking field factories."""

        self._panel = panel
        self._services = services
        self._model_choice_snapshot_controller = model_choice_snapshot_controller
        self._prompt_segment_preset_source = prompt_segment_preset_source

    def build(
        self,
        *,
        field_spec: ResolvedFieldSpec,
        extended_meta: dict[str, Any],
        prompt_field_inputs: Mapping[str, NodeCardPromptFieldInputs] | None,
    ) -> EditorFieldBuildOutcome:
        """Build one field and normalize raw factory results into a typed outcome."""

        prompt_arguments = prompt_field_build_arguments(
            field_spec,
            prompt_field_inputs,
        )
        prompt_services = self._services.prompt
        prompt_runtime = prompt_services.runtime

        def build_field_surface() -> object | None:
            """Invoke the raw field factory inside the typed outcome boundary."""

            return cast(
                object | None,
                build_widget_for_field_spec(
                    parent=self._panel,
                    field_spec=self._field_spec_with_meta(field_spec, extended_meta),
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
                    scheduled_lora_resolver=prompt_arguments.scheduled_lora_resolver,
                    prompt_feature_profile=prompt_arguments.feature_profile,
                    prompt_syntax_profile=prompt_arguments.syntax_profile,
                    prompt_conditioning_context=(prompt_arguments.conditioning_context),
                    prompt_segment_preset_source=self._prompt_segment_preset_source,
                    prompt_spellcheck_service=prompt_runtime.spellcheck_service,
                    model_choice_snapshot_controller=(
                        self._model_choice_snapshot_controller
                    ),
                    thumbnail_asset_repository=(
                        self._services.model.thumbnail_asset_repository
                    ),
                    model_metadata_action_handler=(
                        self._services.model.model_metadata_action_handler
                        or prompt_runtime.model_metadata_action_handler
                    ),
                    empty_model_picker_action=(
                        self._services.model.empty_model_picker_action
                    ),
                    model_updates=self._services.model.model_updates,
                    node_definition_gateway=self._services.node_definition_gateway,
                    prompt_task_executor_factory=cast(
                        PromptEditorTaskExecutorFactory | None,
                        prompt_runtime.prompt_task_executor_factory,
                    ),
                    danbooru_lookup_dispatcher_factory=(
                        prompt_runtime.danbooru_lookup_dispatcher_factory
                    ),
                    model_picker_thumbnail_preload_route_factory=(
                        prompt_services.model_picker_thumbnail_preload_route_factory
                    ),
                ),
            )

        return resolve_editor_field_build(
            field_spec=field_spec,
            build=build_field_surface,
            layout_handled_sentinel=LAYOUT_HANDLED,
        )

    @staticmethod
    def _field_spec_with_meta(
        field_spec: ResolvedFieldSpec,
        meta_info: dict[str, Any],
    ) -> ResolvedFieldSpec:
        """Return a field spec carrying node-card realization metadata."""

        return ResolvedFieldSpec(
            cube_alias=field_spec.cube_alias,
            node_name=field_spec.node_name,
            class_type=field_spec.class_type,
            field_key=field_spec.field_key,
            field_type=field_spec.field_type,
            constraints=dict(field_spec.constraints),
            meta_info=meta_info,
            field_info=list(field_spec.field_info)
            if field_spec.field_info is not None
            else None,
            value=field_spec.value,
            field_behavior=field_spec.field_behavior,
            label_source=field_spec.label_source,
            raw_value=field_spec.raw_value,
            value_source=field_spec.value_source,
        )


__all__ = ["NodeCardFieldFactoryAdapter"]
