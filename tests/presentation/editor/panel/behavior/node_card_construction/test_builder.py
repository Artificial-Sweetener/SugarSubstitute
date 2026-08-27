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

"""Test editor-panel node-card construction through its builder boundary."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from substitute.application.node_behavior import (
    FieldBehavior,
    FieldPresentation,
    ResolvedFieldSpec,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.presentation.editor.panel.prompt.profile_policy import (
    PanelPromptFieldProfileDecision,
)
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)
from tests.support.localization import empty_node_presentation_service


class _StrictNodeCardBuilder:
    """Record production NodeCardBuilder constructor inputs."""

    def __init__(
        self,
        *,
        panel: Any,
        services: Any,
        model_choice_snapshot_controller: Any = None,
        thumbnail_asset_repository: Any = None,
        dimension_preset_source: Any = None,
        node_input_preset_source: Any = None,
        prompt_segment_preset_source: Any = None,
        body_contributors: tuple[Any, ...] = (),
    ) -> None:
        """Store constructor inputs and reject unexpected keyword arguments."""

        self.panel = panel
        self.services = services
        self.node_definition_gateway = services.node_definition_gateway
        runtime = services.prompt.runtime
        self.prompt_autocomplete_gateway = runtime.autocomplete_gateway
        self.prompt_wildcard_catalog_gateway = runtime.wildcard_catalog_gateway
        self.danbooru_url_import_service = runtime.danbooru_url_import_service
        self.danbooru_wiki_service = runtime.danbooru_wiki_service
        self.danbooru_image_preview_service = runtime.danbooru_image_preview_service
        self.danbooru_recent_posts_service = runtime.danbooru_recent_posts_service
        self.prompt_lora_catalog_service = runtime.lora_catalog_service
        self.model_choice_snapshot_controller = model_choice_snapshot_controller
        self.thumbnail_asset_repository = thumbnail_asset_repository
        self.dimension_preset_source = dimension_preset_source
        self.node_input_preset_source = node_input_preset_source
        self.prompt_segment_preset_source = prompt_segment_preset_source
        self.body_contributors = body_contributors
        self.calls: list[dict[str, object]] = []

    def build_node_card(self, **kwargs: object) -> str:
        """Record one build call and return a sentinel wrapper."""

        self.calls.append(kwargs)
        return "node-card"


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def _panel_services(module: ModuleType, panel: SimpleNamespace) -> object:
    """Build the service bundle consumed by the production card builder."""

    return module.EditorPanelServiceBundle(
        node_definition_gateway=panel.node_definition_gateway,
        node_behavior_service=object(),
        node_presentation_service=empty_node_presentation_service(),
        prompt=module.EditorPanelPromptServiceBundle(
            runtime=PromptEditorRuntimeServices(
                autocomplete_gateway=panel.prompt_autocomplete_gateway,
                wildcard_catalog_gateway=panel.prompt_wildcard_catalog_gateway,
                scheduled_lora_service=panel.prompt_scheduled_lora_service,
                lora_catalog_service=panel.prompt_lora_catalog_service,
                danbooru_url_import_service=panel.danbooru_url_import_service,
                danbooru_wiki_service=panel.danbooru_wiki_service,
                danbooru_image_preview_service=panel.danbooru_image_preview_service,
                danbooru_recent_posts_service=panel.danbooru_recent_posts_service,
                spellcheck_service=None,
                thumbnail_asset_repository=panel.thumbnail_asset_repository,
            ),
            scheduled_lora_provider=panel.scheduled_lora_provider,
            feature_profile_service=None,
        ),
        model=module.EditorPanelModelServiceBundle(
            catalog_service=panel.model_catalog_service,
            choice_resolver=panel.model_choice_resolver,
            thumbnail_asset_repository=panel.thumbnail_asset_repository,
        ),
        presets=module.EditorPanelPresetServiceBundle(user_preset_service=None),
    )


def _panel_builder_host(**overrides: object) -> SimpleNamespace:
    """Build a complete façade host for NodeCardBuilder construction."""

    defaults: dict[str, object] = {
        "node_definition_gateway": object(),
        "prompt_autocomplete_gateway": object(),
        "prompt_wildcard_catalog_gateway": object(),
        "danbooru_url_import_service": object(),
        "danbooru_wiki_service": object(),
        "danbooru_image_preview_service": object(),
        "danbooru_recent_posts_service": object(),
        "prompt_lora_catalog_service": object(),
        "scheduled_lora_provider": object(),
        "prompt_scheduled_lora_service": object(),
        "model_catalog_service": object(),
        "model_choice_snapshot_controller": object(),
        "thumbnail_asset_repository": object(),
        "model_choice_resolver": object(),
        "dimension_preset_source": object(),
        "node_input_preset_source": object(),
        "prompt_segment_preset_source": object(),
        "_node_card_body_contributors": (),
        "_preset_context_refresh": SimpleNamespace(
            begin_projection=lambda **_kwargs: None,
            refresh=lambda **_kwargs: None,
        ),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_editor_panel_build_node_card_uses_node_card_builder_constructor_surface(
    monkeypatch: MonkeyPatch,
) -> None:
    """EditorPanel should not pass panel-only services into NodeCardBuilder."""

    module = _panel_module()
    monkeypatch.setattr(module, "NodeCardBuilder", _StrictNodeCardBuilder)
    panel = _panel_builder_host()
    panel._services = _panel_services(module, panel)

    node_card = module.EditorPanel.build_node_card(
        panel,
        node_name="prompt",
        inputs={},
        node_type="CLIPTextEncode",
        field_specs={},
        cube_state={},
        resolved_behavior=object(),
        display_decision=None,
        alias="Cube",
    )

    assert node_card == "node-card"
    assert isinstance(panel._node_card_builder, _StrictNodeCardBuilder)


def test_editor_panel_prepares_node_card_prompt_inputs(
    monkeypatch: MonkeyPatch,
) -> None:
    """EditorPanel should prepare prompt context before invoking NodeCardBuilder."""

    module = _panel_module()
    monkeypatch.setattr(module, "NodeCardBuilder", _StrictNodeCardBuilder)
    prompt_feature_profile = PromptEditorFeatureProfile.enabled_profile(())
    prompt_syntax_profile = PromptSyntaxProfile(enabled_syntaxes=())
    prompt_field_profile = PanelPromptFieldProfileDecision(
        feature_profile=prompt_feature_profile,
        syntax_profile=prompt_syntax_profile,
    )
    scheduled_lora_calls: list[tuple[str | None, str, str]] = []
    prompt_profile_calls: list[tuple[str | None, str, str, dict[str, object]]] = []

    def scheduled_lora_resolver(_text: str) -> tuple[object, ...]:
        """Return no scheduled LoRAs for the prepared resolver sentinel."""

        return ()

    def scheduled_lora_resolver_for_prompt(
        alias: str | None,
        node_name: str,
        field_key: str,
    ) -> object:
        """Record scheduled-LoRA resolver preparation."""

        scheduled_lora_calls.append((alias, node_name, field_key))
        return scheduled_lora_resolver

    def prompt_field_profile_for_prompt(
        alias: str | None,
        node_name: str,
        field_key: str,
        field_style: dict[str, object],
    ) -> PanelPromptFieldProfileDecision:
        """Record prompt field-profile preparation."""

        prompt_profile_calls.append((alias, node_name, field_key, dict(field_style)))
        return prompt_field_profile

    panel = _panel_builder_host(
        scheduled_lora_resolver_for_prompt=scheduled_lora_resolver_for_prompt,
        prompt_field_profile_for_prompt=prompt_field_profile_for_prompt,
    )
    panel._services = _panel_services(module, panel)
    field_behavior = FieldBehavior(
        field_key="text",
        presentation=FieldPresentation.PROMPT_BOX,
        style={"prompt_syntaxes": ["wildcard"]},
    )
    field_spec = ResolvedFieldSpec(
        cube_alias="Cube",
        node_name="prompt",
        class_type="CLIPTextEncode",
        field_key="text",
        field_type="STRING",
        constraints={},
        meta_info={},
        field_info=None,
        value="prompt text",
        field_behavior=field_behavior,
    )

    node_card = module.EditorPanel.build_node_card(
        panel,
        node_name="prompt",
        inputs={"text": "prompt text"},
        node_type="CLIPTextEncode",
        field_specs={"text": field_spec},
        cube_state={},
        resolved_behavior=object(),
        display_decision=None,
        alias="Cube",
    )

    assert node_card == "node-card"
    assert scheduled_lora_calls == [("Cube", "prompt", "text")]
    assert prompt_profile_calls == [
        ("Cube", "prompt", "text", {"prompt_syntaxes": ["wildcard"]})
    ]
    prompt_inputs = panel._node_card_builder.calls[0]["prompt_field_inputs"]
    assert prompt_inputs["text"].scheduled_lora_resolver is scheduled_lora_resolver
    assert prompt_inputs["text"].prompt_field_profile is prompt_field_profile
    assert prompt_inputs["text"].prompt_field_profile.feature_profile is (
        prompt_feature_profile
    )
    assert prompt_inputs["text"].prompt_field_profile.syntax_profile is (
        prompt_syntax_profile
    )
