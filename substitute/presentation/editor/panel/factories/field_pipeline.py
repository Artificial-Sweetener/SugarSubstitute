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

"""Coordinate editor field widget construction through the panel factory owners."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from qfluentwidgets import CheckBox, LineEdit  # type: ignore[import-untyped]

from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.application.node_behavior import (
    FieldBehavior,
    FieldPresentation,
    ResolvedFieldSpec,
)
from substitute.application.overrides.control_registry_service import (
    get_registered_widget_builder as _get_registered_widget_builder,
)
from substitute.application.ports import (
    NodeDefinitionGateway,
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptLoraCatalogLookup,
    PromptScheduledLora,
    PromptScheduledLoraService,
    PromptSpellcheckService,
    PromptSyntaxProfile,
)
from substitute.presentation.editor.panel.factories import (
    choice_factory as _choice_factory,
)
from substitute.presentation.editor.panel.factories import (
    numeric_factory as _numeric_factory,
)
from substitute.presentation.editor.panel.factories.choice_factory import (
    ChoiceFieldBuildRequest,
    ChoiceFieldFactory,
)
from substitute.presentation.editor.panel.factories.field_factory import (
    EditorFieldBuildRequest,
    EditorWidgetFactory,
)
from substitute.presentation.editor.panel.factories.image_factory import (
    ImageMaskFieldBuildRequest,
    ImageMaskFieldFactory,
)
from substitute.presentation.editor.panel.factories.numeric_factory import (
    NumericFieldBuildRequest,
    NumericFieldFactory,
)
from substitute.presentation.editor.panel.factories.prompt_factory import (
    PromptEditorFieldBuildRequest,
    PromptEditorFieldFactory,
)
from substitute.presentation.editor.panel.factories.registry import (
    EditorFieldFactoryRegistry,
)
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshotController,
    PanelModelChoiceSnapshotRequest,
)
from substitute.presentation.editor.panel.prompt_profile_policy import (
    PanelPromptProfilePolicy,
)
from substitute.presentation.editor.panel.service_bundle import (
    DanbooruWikiLookupDispatcherFactory,
    ModelPickerThumbnailPreloadRouteFactory,
    PromptEditorTaskExecutorFactory,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetSource,
)

FIELD_FACTORY_REGISTRY = EditorFieldFactoryRegistry()
PROMPT_EDITOR_FIELD_FACTORY = PromptEditorFieldFactory()
CHOICE_FIELD_FACTORY = ChoiceFieldFactory()
NUMERIC_FIELD_FACTORY = NumericFieldFactory()
IMAGE_MASK_FIELD_FACTORY = ImageMaskFieldFactory()
PROMPT_PROFILE_POLICY = PanelPromptProfilePolicy()
LAYOUT_HANDLED = object()


def register_factory(factory: EditorWidgetFactory) -> EditorWidgetFactory:
    """Register one generic widget factory in evaluation order."""

    return FIELD_FACTORY_REGISTRY.register_callable_factory(factory)


def get_registered_widget_builder(control: str) -> Callable[..., object] | None:
    """Return a custom widget builder registered for a control key, if available."""

    return _get_registered_widget_builder(control)


def build_widget_for_field_behavior(
    *,
    parent: Any,
    field_behavior: FieldBehavior,
    node_name: str,
    key: str,
    value: object,
    field_meta: dict[str, object],
    prompt_autocomplete_gateway: PromptAutocompleteGateway,
    prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
    danbooru_url_import_service: DanbooruUrlImportService | None = None,
    danbooru_wiki_service: DanbooruWikiContentService | None = None,
    danbooru_image_preview_service: DanbooruImagePreviewService | None = None,
    danbooru_recent_posts_service: DanbooruRecentPostsService | None = None,
    prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
    prompt_scheduled_lora_service: PromptScheduledLoraService | None = None,
    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]]
    | None = None,
    prompt_feature_profile: PromptEditorFeatureProfile | None = None,
    prompt_syntax_profile: PromptSyntaxProfile | None = None,
    prompt_segment_preset_source: PromptSegmentPresetSource | None = None,
    prompt_spellcheck_service: PromptSpellcheckService | None = None,
    model_choice_snapshot_controller: PanelModelChoiceSnapshotController | None = None,
    thumbnail_asset_repository: ThumbnailAssetRepository | None = None,
    model_metadata_action_handler: ModelMetadataContextActionHandler | None = None,
    node_definition_gateway: NodeDefinitionGateway | None = None,
    prompt_task_executor_factory: PromptEditorTaskExecutorFactory | None = None,
    danbooru_lookup_dispatcher_factory: (
        DanbooruWikiLookupDispatcherFactory | None
    ) = None,
    model_picker_thumbnail_preload_route_factory: (
        ModelPickerThumbnailPreloadRouteFactory | None
    ) = None,
    **kwargs: object,
) -> Any:
    """Build one widget using resolved field behavior plus generic type factories."""

    if field_behavior.presentation == FieldPresentation.PROMPT_BOX:
        prompt_profile_decision = PROMPT_PROFILE_POLICY.prepare_prompt_field_profile(
            field_style=field_behavior.style,
            feature_profile=prompt_feature_profile,
            syntax_profile=prompt_syntax_profile,
        )
        return PROMPT_EDITOR_FIELD_FACTORY.build_field_widget(
            PromptEditorFieldBuildRequest(
                parent=parent,
                field_behavior=field_behavior,
                node_name=node_name,
                key=key,
                value=value,
                field_meta=field_meta,
                node_type=kwargs.get("node_type", ""),
                prompt_autocomplete_gateway=prompt_autocomplete_gateway,
                prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
                danbooru_url_import_service=danbooru_url_import_service,
                danbooru_wiki_service=danbooru_wiki_service,
                danbooru_image_preview_service=danbooru_image_preview_service,
                danbooru_recent_posts_service=danbooru_recent_posts_service,
                prompt_lora_catalog_service=prompt_lora_catalog_service,
                prompt_scheduled_lora_service=prompt_scheduled_lora_service,
                scheduled_lora_resolver=scheduled_lora_resolver,
                prompt_feature_profile=prompt_profile_decision.feature_profile,
                prompt_syntax_profile=prompt_profile_decision.syntax_profile,
                prompt_segment_preset_source=prompt_segment_preset_source,
                prompt_spellcheck_service=prompt_spellcheck_service,
                thumbnail_asset_repository=thumbnail_asset_repository,
                model_metadata_action_handler=model_metadata_action_handler,
                prompt_task_executor_factory=prompt_task_executor_factory,
                danbooru_lookup_dispatcher_factory=(danbooru_lookup_dispatcher_factory),
            )
        )

    image_mask_result = IMAGE_MASK_FIELD_FACTORY.build_field_widget(
        ImageMaskFieldBuildRequest(
            parent=parent,
            field_behavior=field_behavior,
            node_name=node_name,
            key=key,
            value=value,
            field_meta=field_meta,
        )
    )
    if image_mask_result is not None:
        return image_mask_result

    cube_alias = field_meta.get("cube_alias")
    model_choice_snapshot = (
        model_choice_snapshot_controller.snapshot_for_field(
            PanelModelChoiceSnapshotRequest(
                field_behavior=field_behavior,
                node_name=node_name,
                key=key,
                value=value,
                node_type=kwargs.get("node_type"),
                field_type=kwargs.get("field_type"),
                field_info=kwargs.get("field_info"),
                node_definition_gateway=node_definition_gateway,
                cube_alias=cube_alias if isinstance(cube_alias, str) else None,
                thumbnail_repository_available=(thumbnail_asset_repository is not None),
            )
        )
        if model_choice_snapshot_controller is not None
        else None
    )
    choice_result = CHOICE_FIELD_FACTORY.build_field_widget(
        ChoiceFieldBuildRequest(
            parent=parent,
            field_behavior=field_behavior,
            node_name=node_name,
            key=key,
            value=value,
            field_meta=field_meta,
            model_choice_snapshot=model_choice_snapshot,
            thumbnail_asset_repository=thumbnail_asset_repository,
            model_metadata_action_handler=model_metadata_action_handler,
            node_definition_gateway=node_definition_gateway,
            thumbnail_preload_route_factory=(
                model_picker_thumbnail_preload_route_factory
            ),
            node_type=kwargs.get("node_type"),
            field_type=kwargs.get("field_type"),
            field_info=kwargs.get("field_info"),
        )
    )
    if choice_result is not None:
        return choice_result

    if field_behavior.presentation == FieldPresentation.CUSTOM:
        control_name = field_behavior.control_name
        if isinstance(control_name, str):
            builder = get_registered_widget_builder(control_name)
            if builder is not None:
                constraints = kwargs.get("constraints", {})
                return builder(
                    parent,
                    value,
                    constraints if isinstance(constraints, dict) else {},
                    {
                        "control": control_name,
                        "style": dict(field_behavior.style),
                        "label": field_behavior.label_override,
                        "column_span": field_behavior.column_span,
                    },
                )

    raw_constraints = kwargs.get("constraints")
    constraints = raw_constraints if isinstance(raw_constraints, dict) else {}

    numeric_result = NUMERIC_FIELD_FACTORY.build_field_widget(
        NumericFieldBuildRequest(
            parent=parent,
            node_name=node_name,
            key=key,
            value=value,
            field_meta=field_meta,
            field_type=kwargs.get("field_type"),
            field_presentation=field_behavior.presentation,
            constraints=constraints,
        )
    )
    if numeric_result is not None:
        return numeric_result

    return FIELD_FACTORY_REGISTRY.build_widget(
        EditorFieldBuildRequest(
            parent=parent,
            node_name=node_name,
            key=key,
            value=value,
            field_meta=field_meta,
            node_definition_gateway=node_definition_gateway,
            node_type=kwargs.get("node_type"),
            field_type=kwargs.get("field_type"),
            field_info=kwargs.get("field_info"),
            constraints=constraints,
            extra_kwargs=kwargs,
        )
    )


def build_widget_for_field_spec(
    *,
    parent: Any,
    field_spec: ResolvedFieldSpec,
    prompt_autocomplete_gateway: PromptAutocompleteGateway,
    prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
    danbooru_url_import_service: DanbooruUrlImportService | None = None,
    danbooru_wiki_service: DanbooruWikiContentService | None = None,
    danbooru_image_preview_service: DanbooruImagePreviewService | None = None,
    danbooru_recent_posts_service: DanbooruRecentPostsService | None = None,
    prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
    prompt_scheduled_lora_service: PromptScheduledLoraService | None = None,
    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]]
    | None = None,
    prompt_feature_profile: PromptEditorFeatureProfile | None = None,
    prompt_syntax_profile: PromptSyntaxProfile | None = None,
    prompt_segment_preset_source: PromptSegmentPresetSource | None = None,
    prompt_spellcheck_service: PromptSpellcheckService | None = None,
    model_choice_snapshot_controller: PanelModelChoiceSnapshotController | None = None,
    thumbnail_asset_repository: ThumbnailAssetRepository | None = None,
    model_metadata_action_handler: ModelMetadataContextActionHandler | None = None,
    node_definition_gateway: NodeDefinitionGateway | None = None,
    prompt_task_executor_factory: PromptEditorTaskExecutorFactory | None = None,
    danbooru_lookup_dispatcher_factory: (
        DanbooruWikiLookupDispatcherFactory | None
    ) = None,
    model_picker_thumbnail_preload_route_factory: (
        ModelPickerThumbnailPreloadRouteFactory | None
    ) = None,
    field_meta_overrides: dict[str, object] | None = None,
) -> Any:
    """Build one widget from a resolved field spec through the shared behavior path."""

    field_meta = dict(field_spec.meta_info)
    if field_meta_overrides:
        field_meta.update(field_meta_overrides)
    return build_widget_for_field_behavior(
        parent=parent,
        field_behavior=field_spec.field_behavior,
        node_name=field_spec.node_name,
        key=field_spec.field_key,
        value=field_spec.value,
        field_meta=field_meta,
        prompt_autocomplete_gateway=prompt_autocomplete_gateway,
        prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
        danbooru_url_import_service=danbooru_url_import_service,
        danbooru_wiki_service=danbooru_wiki_service,
        danbooru_image_preview_service=danbooru_image_preview_service,
        danbooru_recent_posts_service=danbooru_recent_posts_service,
        prompt_lora_catalog_service=prompt_lora_catalog_service,
        prompt_scheduled_lora_service=prompt_scheduled_lora_service,
        scheduled_lora_resolver=scheduled_lora_resolver,
        prompt_feature_profile=prompt_feature_profile,
        prompt_syntax_profile=prompt_syntax_profile,
        prompt_segment_preset_source=prompt_segment_preset_source,
        prompt_spellcheck_service=prompt_spellcheck_service,
        model_choice_snapshot_controller=model_choice_snapshot_controller,
        thumbnail_asset_repository=thumbnail_asset_repository,
        model_metadata_action_handler=model_metadata_action_handler,
        node_definition_gateway=node_definition_gateway,
        prompt_task_executor_factory=prompt_task_executor_factory,
        danbooru_lookup_dispatcher_factory=danbooru_lookup_dispatcher_factory,
        model_picker_thumbnail_preload_route_factory=(
            model_picker_thumbnail_preload_route_factory
        ),
        node_type=field_spec.class_type,
        field_type=field_spec.field_type,
        field_info=field_spec.field_info,
        constraints=field_spec.constraints,
    )


widget_factory_spinner_slider = register_factory(
    _numeric_factory.widget_factory_spinner_slider
)


@register_factory
def widget_factory_bool(
    parent: Any,
    node_name: str,
    key: str,
    value: object,
    field_meta: dict[str, object],
    **kwargs: object,
) -> object | None:
    """Build a checkbox for BOOLEAN field specs."""

    _ = (node_name, key, field_meta)
    if kwargs.get("field_type") != "BOOLEAN":
        return None

    field = CheckBox("Enable", parent)
    field.setChecked(bool(value))
    return cast(object, field)


widget_factory_seedbox = register_factory(_numeric_factory.widget_factory_seedbox)
widget_factory_int = register_factory(_numeric_factory.widget_factory_int)
widget_factory_float = register_factory(_numeric_factory.widget_factory_float)
widget_factory_list_str = register_factory(_choice_factory.widget_factory_list_str)


@register_factory
def widget_factory_string(
    parent: Any,
    node_name: str,
    key: str,
    value: object,
    field_meta: dict[str, object],
    **kwargs: object,
) -> object | None:
    """Build a line edit for STRING field specs."""

    _ = (node_name, key, field_meta)
    if kwargs.get("field_type") != "STRING":
        return None

    field = LineEdit(parent)
    field.setText(str(value))
    return cast(object, field)


def _register_control_registry_builders() -> None:
    """Register builtin editor control builders without infrastructure imports."""

    _numeric_factory.register_numeric_control_builders()


_register_control_registry_builders()
