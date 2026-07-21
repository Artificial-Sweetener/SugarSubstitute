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

"""Helpers for constructing node-card builders in focused tests."""

from __future__ import annotations

from typing import Any, cast

from substitute.application.localization import NodePresentationService
from substitute.application.node_behavior import NodeBehaviorService
from substitute.presentation.editor.panel.node_card_builder import NodeCardBuilder
from substitute.presentation.editor.panel.service_bundle import (
    EditorPanelModelServiceBundle,
    EditorPanelPresetServiceBundle,
    EditorPanelPromptServiceBundle,
    EditorPanelServiceBundle,
)
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)
from tests.execution_test_helpers import immediate_editor_panel_execution_factories
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)
from tests.localization_testing import empty_node_presentation_service


class NoopNodeBehaviorService:
    """Provide the activation API needed by isolated node-card tests."""

    def set_node_activation_override(
        self, _cube_state: object, _node_name: str, _override: object
    ) -> None:
        """Ignore activation writes when a focused test omits the service."""


def node_card_service_bundle(
    *,
    panel: Any,
    node_definition_gateway: Any,
    prompt_autocomplete_gateway: Any | None = None,
    prompt_wildcard_catalog_gateway: Any | None = None,
    thumbnail_asset_repository: Any | None = None,
    prompt_lora_catalog_service: Any | None = None,
    danbooru_url_import_service: Any | None = None,
    danbooru_wiki_service: Any | None = None,
    danbooru_image_preview_service: Any | None = None,
    danbooru_recent_posts_service: Any | None = None,
    node_presentation_service: NodePresentationService | None = None,
) -> EditorPanelServiceBundle:
    """Build a production-shaped service bundle for node-card tests."""

    node_behavior_service = getattr(panel, "node_behavior_service", None)
    if node_behavior_service is None:
        node_behavior_service = cast(NodeBehaviorService, NoopNodeBehaviorService())
    execution_factories = immediate_editor_panel_execution_factories()
    return EditorPanelServiceBundle(
        node_definition_gateway=node_definition_gateway,
        node_behavior_service=node_behavior_service,
        node_presentation_service=(
            node_presentation_service or empty_node_presentation_service()
        ),
        prompt=EditorPanelPromptServiceBundle(
            runtime=PromptEditorRuntimeServices(
                autocomplete_gateway=(
                    prompt_autocomplete_gateway or EmptyPromptAutocompleteGateway()
                ),
                wildcard_catalog_gateway=(
                    prompt_wildcard_catalog_gateway
                    or EmptyPromptWildcardCatalogGateway()
                ),
                danbooru_url_import_service=danbooru_url_import_service,
                danbooru_wiki_service=danbooru_wiki_service,
                danbooru_image_preview_service=danbooru_image_preview_service,
                danbooru_recent_posts_service=danbooru_recent_posts_service,
                lora_catalog_service=prompt_lora_catalog_service,
                scheduled_lora_service=getattr(
                    panel,
                    "prompt_scheduled_lora_service",
                    None,
                ),
                spellcheck_service=getattr(panel, "prompt_spellcheck_service", None),
                thumbnail_asset_repository=thumbnail_asset_repository,
                prompt_task_executor_factory=(
                    execution_factories.prompt_task_executor_factory
                ),
                danbooru_lookup_dispatcher_factory=(
                    execution_factories.danbooru_lookup_dispatcher_factory
                ),
            ),
            feature_profile_service=getattr(
                panel,
                "prompt_feature_profile_service",
                None,
            ),
            model_picker_thumbnail_preload_route_factory=(
                execution_factories.model_picker_thumbnail_preload_route_factory
            ),
        ),
        model=EditorPanelModelServiceBundle(
            thumbnail_asset_repository=thumbnail_asset_repository,
        ),
        presets=EditorPanelPresetServiceBundle(),
    )


def build_node_card_builder(
    panel: Any,
    node_definition_gateway: Any,
    prompt_autocomplete_gateway: Any | None = None,
    prompt_wildcard_catalog_gateway: Any | None = None,
    **kwargs: Any,
) -> NodeCardBuilder:
    """Return a `NodeCardBuilder` using the explicit service-bundle surface."""

    thumbnail_asset_repository = kwargs.pop("thumbnail_asset_repository", None)
    prompt_lora_catalog_service = kwargs.pop("prompt_lora_catalog_service", None)
    node_presentation_service = kwargs.pop("node_presentation_service", None)
    return NodeCardBuilder(
        panel=panel,
        services=node_card_service_bundle(
            panel=panel,
            node_definition_gateway=node_definition_gateway,
            prompt_autocomplete_gateway=prompt_autocomplete_gateway,
            prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
            thumbnail_asset_repository=thumbnail_asset_repository,
            prompt_lora_catalog_service=prompt_lora_catalog_service,
            node_presentation_service=node_presentation_service,
            danbooru_url_import_service=kwargs.pop("danbooru_url_import_service", None),
            danbooru_wiki_service=kwargs.pop("danbooru_wiki_service", None),
            danbooru_image_preview_service=kwargs.pop(
                "danbooru_image_preview_service",
                None,
            ),
            danbooru_recent_posts_service=kwargs.pop(
                "danbooru_recent_posts_service",
                None,
            ),
        ),
        **kwargs,
    )
