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

"""Contract tests for the panel prompt editor field factory."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from substitute.application.node_behavior import FieldBehavior, FieldPresentation
from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptAutocompleteSuggestion,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptFeatureDecision,
    PromptSyntaxProfile,
)
import substitute.presentation.editor.panel.factories.prompt_factory as prompt_factory
from substitute.presentation.editor.panel.factories.prompt_factory import (
    PromptEditorFieldBuildRequest,
    PromptEditorFieldFactory,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


class _FakePromptEditor:
    """PromptEditor test double that records constructor inputs and source text."""

    def __init__(
        self,
        _parent: object = None,
        *,
        prompt_autocomplete_gateway: object = None,
        prompt_wildcard_catalog_gateway: object = None,
        prompt_syntax_profile: object = None,
        danbooru_url_import_service: object = None,
        danbooru_wiki_service: object = None,
        danbooru_image_preview_service: object = None,
        danbooru_recent_posts_service: object = None,
        prompt_lora_catalog_service: object = None,
        prompt_scheduled_lora_service: object = None,
        scheduled_lora_resolver: object = None,
        prompt_feature_profile: object = None,
        prompt_segment_preset_source: object = None,
        prompt_spellcheck_service: object = None,
        thumbnail_asset_repository: object = None,
        model_metadata_action_handler: object = None,
        prompt_task_executor_factory: object = None,
        danbooru_lookup_dispatcher_factory: object = None,
        maximum_visible_lines: object = "prompt-default",
    ) -> None:
        """Record all prompt construction inputs."""

        self.source_text = ""
        self.plain_text = ""
        self.prompt_autocomplete_gateway = prompt_autocomplete_gateway
        self.prompt_wildcard_catalog_gateway = prompt_wildcard_catalog_gateway
        self.prompt_syntax_profile = prompt_syntax_profile
        self.danbooru_url_import_service = danbooru_url_import_service
        self.danbooru_wiki_service = danbooru_wiki_service
        self.danbooru_image_preview_service = danbooru_image_preview_service
        self.danbooru_recent_posts_service = danbooru_recent_posts_service
        self.prompt_lora_catalog_service = prompt_lora_catalog_service
        self.prompt_scheduled_lora_service = prompt_scheduled_lora_service
        self.scheduled_lora_resolver = scheduled_lora_resolver
        self.prompt_feature_profile = prompt_feature_profile
        self.prompt_segment_preset_source = prompt_segment_preset_source
        self.prompt_spellcheck_service = prompt_spellcheck_service
        self.thumbnail_asset_repository = thumbnail_asset_repository
        self.model_metadata_action_handler = model_metadata_action_handler
        self.prompt_task_executor_factory = prompt_task_executor_factory
        self.danbooru_lookup_dispatcher_factory = danbooru_lookup_dispatcher_factory
        self.maximum_visible_lines = maximum_visible_lines

    def replaceBaselineSourceText(self, text: str) -> None:  # noqa: N802
        """Record source-baseline prompt text."""

        self.source_text = text

    def setPlainText(self, text: str) -> None:  # noqa: N802
        """Record fallback plain text assignment."""

        self.plain_text = text


class _FakePromptAutocompleteGateway:
    """Return empty autocomplete results for prompt factory tests."""

    @staticmethod
    def search(
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no suggestions while satisfying the gateway protocol."""

        _ = (prefix, limit)
        return ()


def test_build_prompt_editor_widget_sets_baseline_text_and_gateways(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prompt construction should initialize source text and inject gateways."""

    monkeypatch.setattr(prompt_factory, "PromptEditor", _FakePromptEditor)
    autocomplete_gateway = _FakePromptAutocompleteGateway()
    wildcard_gateway = object()
    syntax_profile = PromptSyntaxProfile(enabled_syntaxes=("emphasis",))
    feature_profile = PromptEditorFeatureProfile.enabled_profile(
        (PromptEditorFeature.EMPHASIS,)
    )

    widget = prompt_factory.build_prompt_editor_widget(
        parent=cast("QWidget", None),
        value="hello world",
        prompt_autocomplete_gateway=autocomplete_gateway,
        prompt_wildcard_catalog_gateway=cast(
            PromptWildcardCatalogGateway, wildcard_gateway
        ),
        prompt_syntax_profile=syntax_profile,
        prompt_feature_profile=feature_profile,
    )

    assert isinstance(widget, _FakePromptEditor)
    assert widget.source_text == "hello world"
    assert widget.plain_text == ""
    assert widget.prompt_autocomplete_gateway is autocomplete_gateway
    assert widget.prompt_wildcard_catalog_gateway is wildcard_gateway
    assert widget.prompt_syntax_profile is syntax_profile
    assert widget.prompt_feature_profile is feature_profile
    assert widget.maximum_visible_lines == "prompt-default"


def test_prompt_editor_field_factory_uses_prepared_feature_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prepared Phase 13 prompt profiles should pass through unchanged."""

    monkeypatch.setattr(prompt_factory, "PromptEditor", _FakePromptEditor)
    feature_profile = PromptEditorFeatureProfile(
        decisions=(
            PromptFeatureDecision(
                feature=PromptEditorFeature.EMPHASIS,
                enabled=True,
            ),
        )
    )
    syntax_profile = PromptSyntaxProfile(enabled_syntaxes=("emphasis",))

    widget = PromptEditorFieldFactory().build_field_widget(
        PromptEditorFieldBuildRequest(
            parent=cast("QWidget", None),
            field_behavior=FieldBehavior(
                field_key="prompt",
                presentation=FieldPresentation.PROMPT_BOX,
                style={"prompt_syntaxes": ["wildcard"]},
            ),
            node_name="CLIPTextEncode",
            key="text",
            value="prompt text",
            field_meta={"cube_alias": "cube-a"},
            node_type="CLIPTextEncode",
            prompt_autocomplete_gateway=cast(
                PromptAutocompleteGateway, _FakePromptAutocompleteGateway()
            ),
            prompt_wildcard_catalog_gateway=cast(
                PromptWildcardCatalogGateway, object()
            ),
            prompt_feature_profile=feature_profile,
            prompt_syntax_profile=syntax_profile,
        )
    )

    assert isinstance(widget, _FakePromptEditor)
    assert widget.prompt_feature_profile is feature_profile
    assert widget.prompt_syntax_profile is syntax_profile


def test_prompt_editor_field_factory_requires_prepared_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prompt field construction should consume prepared profile inputs."""

    monkeypatch.setattr(prompt_factory, "PromptEditor", _FakePromptEditor)
    feature_profile = PromptEditorFeatureProfile(
        decisions=(
            PromptFeatureDecision(
                feature=PromptEditorFeature.WILDCARD_SYNTAX,
                enabled=True,
            ),
        )
    )
    syntax_profile = PromptSyntaxProfile(enabled_syntaxes=("wildcard",))

    widget = PromptEditorFieldFactory().build_field_widget(
        PromptEditorFieldBuildRequest(
            parent=cast("QWidget", None),
            field_behavior=FieldBehavior(
                field_key="prompt",
                presentation=FieldPresentation.PROMPT_BOX,
                style={"prompt_syntaxes": ["emphasis", "wildcard"]},
            ),
            node_name="CLIPTextEncode",
            key="text",
            value="prompt text",
            field_meta={},
            prompt_autocomplete_gateway=cast(
                PromptAutocompleteGateway, _FakePromptAutocompleteGateway()
            ),
            prompt_wildcard_catalog_gateway=cast(
                PromptWildcardCatalogGateway, object()
            ),
            prompt_feature_profile=feature_profile,
            prompt_syntax_profile=syntax_profile,
        )
    )

    assert isinstance(widget, _FakePromptEditor)
    assert widget.prompt_feature_profile is feature_profile
    assert widget.prompt_syntax_profile is syntax_profile


def test_prompt_editor_field_factory_declines_non_prompt_or_non_string_fields() -> None:
    """Only prompt-box string fields should construct prompt editors."""

    factory = PromptEditorFieldFactory()
    feature_profile = PromptEditorFeatureProfile.enabled_profile(())
    syntax_profile = PromptSyntaxProfile(enabled_syntaxes=())
    base_request = PromptEditorFieldBuildRequest(
        parent=cast("QWidget", None),
        field_behavior=FieldBehavior(
            field_key="prompt",
            presentation=FieldPresentation.PROMPT_BOX,
        ),
        node_name="CLIPTextEncode",
        key="text",
        value=42,
        field_meta={},
        prompt_autocomplete_gateway=cast(
            PromptAutocompleteGateway, _FakePromptAutocompleteGateway()
        ),
        prompt_wildcard_catalog_gateway=cast(PromptWildcardCatalogGateway, object()),
        prompt_feature_profile=feature_profile,
        prompt_syntax_profile=syntax_profile,
    )

    assert factory.build_field_widget(base_request) is None
    assert (
        factory.build_field_widget(
            PromptEditorFieldBuildRequest(
                parent=base_request.parent,
                field_behavior=FieldBehavior(field_key="seed"),
                node_name=base_request.node_name,
                key=base_request.key,
                value="prompt",
                field_meta=base_request.field_meta,
                prompt_autocomplete_gateway=base_request.prompt_autocomplete_gateway,
                prompt_wildcard_catalog_gateway=(
                    base_request.prompt_wildcard_catalog_gateway
                ),
                prompt_feature_profile=feature_profile,
                prompt_syntax_profile=syntax_profile,
            )
        )
        is None
    )
