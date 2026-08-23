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

"""Verify inferred catalog-backed model-choice routes."""

from __future__ import annotations

from __future__ import annotations
from __future__ import annotations
from types import SimpleNamespace
import pytest
from substitute.application.node_behavior import FieldBehavior
import substitute.presentation.editor.panel.factories.choice_factory as choice_factory
import substitute.presentation.editor.panel.factories.field_pipeline as factories
from ..choice.characterization_support import (
    _FakeComboBox,
    _FakeModelCatalog,
    _FakeModelPickerField,
    _FakePromptAutocompleteGateway,
    _model_choice_controller,
    _model_item,
    _rich_choice_resolver,
    _wildcard_gateway,
)


def test_build_widget_for_field_behavior_builds_rich_picker_for_lora_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model-backed LIST values should build the rich picker without node patches."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _FakeModelCatalog(
        (
            _model_item("loras", "animeLineart.safetensors", "Anime Lineart"),
            _model_item("loras", "stylePack.safetensors", "Style Pack"),
        )
    )
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="lora_name"),
        node_name="lora_loader",
        key="lora_name",
        value="animeLineart.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="SomeLoraLoader",
        field_info=[
            ["animeLineart.safetensors", "stylePack.safetensors"],
            {},
        ],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.matched_kinds == ("loras",)
    assert [item.value for item in widget.resolution.items] == [
        "animeLineart.safetensors",
        "stylePack.safetensors",
    ]


def test_build_widget_for_field_behavior_keeps_unverified_model_list_as_combo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model-like field name should not create a picker without catalog evidence."""

    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)
    catalog = _FakeModelCatalog(())
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent=SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={}),
        field_behavior=FieldBehavior(field_key="ckpt_name"),
        node_name="checkpoint",
        key="ckpt_name",
        value="base-a.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="CheckpointLoaderSimple",
        field_info=[
            ["base-a.safetensors", "base-b.safetensors"],
            {},
        ],
    )

    assert isinstance(widget, _FakeComboBox)
    assert widget.items == [
        "base-a.safetensors",
        "base-b.safetensors",
    ]


def test_model_list_becomes_picker_after_catalog_evidence_is_prepared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later projection should use a picker once exact catalog evidence exists."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)
    catalog = _FakeModelCatalog(())
    resolver = _rich_choice_resolver(catalog)
    controller = _model_choice_controller(catalog, resolver)
    parent = SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={})

    first_widget = factories.build_widget_for_field_behavior(
        parent=parent,
        field_behavior=FieldBehavior(field_key="ckpt_name"),
        node_name="checkpoint",
        key="ckpt_name",
        value="base-a.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=controller,
        field_type="LIST",
        node_type="CheckpointLoaderSimple",
        field_info=[
            ["base-a.safetensors", "base-b.safetensors"],
            {},
        ],
    )
    catalog.replace_items(
        (
            _model_item("checkpoints", "base-a.safetensors", "Base A"),
            _model_item("checkpoints", "base-b.safetensors", "Base B"),
        )
    )

    second_widget = factories.build_widget_for_field_behavior(
        parent=parent,
        field_behavior=FieldBehavior(field_key="ckpt_name"),
        node_name="checkpoint",
        key="ckpt_name",
        value="base-a.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=controller,
        field_type="LIST",
        node_type="CheckpointLoaderSimple",
        field_info=[
            ["base-a.safetensors", "base-b.safetensors"],
            {},
        ],
    )

    assert isinstance(first_widget, _FakeComboBox)
    assert isinstance(second_widget, _FakeModelPickerField)
    assert second_widget.resolution.matched_kinds == ("checkpoints",)
    assert second_widget.resolution.enriched_count == 2


def test_build_widget_for_field_behavior_recovers_from_stale_empty_rich_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model LIST rendering should recover when the resolver was loaded empty early."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _FakeModelCatalog(())
    resolver = _rich_choice_resolver(catalog)
    resolver.resolve(("base-a.safetensors", "base-b.safetensors"))
    catalog.replace_items(
        (
            _model_item("checkpoints", "base-a.safetensors", "Base A"),
            _model_item("checkpoints", "base-b.safetensors", "Base B"),
        )
    )

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="ckpt_name"),
        node_name="checkpoint",
        key="ckpt_name",
        value="base-a.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="CheckpointLoaderSimple",
        field_info=[
            ["base-a.safetensors", "base-b.safetensors"],
            {},
        ],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.matched_kinds == ("checkpoints",)


def test_build_widget_for_field_behavior_builds_rich_picker_for_anima_diffusion_model_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anima diffusion model LIST values should build the shared rich picker."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _FakeModelCatalog(
        (
            _model_item(
                "diffusion_models",
                "Anima\\anima_base_V10.safetensors",
                "Anima Base",
            ),
            _model_item(
                "diffusion_models",
                "Anima\\animaOfficial_preview3Base.safetensors",
                "Anima Preview",
            ),
        )
    )
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="diffusion_model"),
        node_name="load_anima",
        key="diffusion_model",
        value="Anima\\anima_base_V10.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="SimpleSyrup.SimpleLoadAnima",
        field_info=[
            [
                "Anima\\anima_base_V10.safetensors",
                "Anima\\animaOfficial_preview3Base.safetensors",
            ],
            {},
        ],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.matched_kinds == ("diffusion_models",)
    assert widget.currentText() == "Anima\\anima_base_V10.safetensors"
    assert [item.value for item in widget.resolution.items] == [
        "Anima\\anima_base_V10.safetensors",
        "Anima\\animaOfficial_preview3Base.safetensors",
    ]


def test_build_widget_for_field_behavior_attempts_rich_picker_for_generic_diffusion_model_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generic diffusion model key fragments should attempt rich picker enrichment."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _FakeModelCatalog(
        (
            _model_item(
                "diffusion_models",
                "models\\diffusion-a.safetensors",
                "Diffusion A",
            ),
            _model_item(
                "diffusion_models",
                "models\\diffusion-b.safetensors",
                "Diffusion B",
            ),
        )
    )
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="diffusion_model"),
        node_name="load_diffusion",
        key="diffusion_model",
        value="models\\diffusion-a.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="SomeDiffusionLoader",
        field_info=[
            [
                "models\\diffusion-a.safetensors",
                "models\\diffusion-b.safetensors",
            ],
            {},
        ],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.matched_kinds == ("diffusion_models",)
    assert widget.currentText() == "models\\diffusion-a.safetensors"


def test_build_widget_for_field_behavior_keeps_vae_literals_in_rich_picker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VAE LIST values should qualify while special literals remain choices."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _FakeModelCatalog(
        (
            _model_item("vae", "ClearVAE.safetensors", "ClearVAE"),
            _model_item("vae", "Illustrious\\neptunia.safetensors", "Neptunia"),
        )
    )
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="vae_name"),
        node_name="vae",
        key="vae_name",
        value="pixel_space",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="VAELoader",
        field_info=[
            [
                "ClearVAE.safetensors",
                "Illustrious\\neptunia.safetensors",
                "pixel_space",
            ],
            {},
        ],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.items[2].value == "pixel_space"
    assert widget.resolution.items[2].is_enriched is False


def test_model_picker_eligibility_follows_supported_comfy_catalog_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only choices belonging to supported Comfy model catalogs should use pickers."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)
    catalog = _FakeModelCatalog(
        (
            _model_item(
                "diffusion_models",
                "Anima\\anima-a.safetensors",
                "Anima A",
            ),
            _model_item(
                "diffusion_models",
                "Anima\\anima-b.safetensors",
                "Anima B",
            ),
            _model_item("vae", "ClearVAE.safetensors", "Clear VAE"),
            _model_item("vae", "qwen\\qwen-image-vae.safetensors", "Qwen VAE"),
            _model_item("text_encoders", "qwen\\encoder-a.safetensors", "Encoder A"),
            _model_item("text_encoders", "qwen\\encoder-b.safetensors", "Encoder B"),
            _model_item("controlnet", "control-a.safetensors", "ControlNet A"),
            _model_item("controlnet", "control-b.safetensors", "ControlNet B"),
            _model_item("upscale_models", "upscale-a.pth", "Upscaler A"),
            _model_item("upscale_models", "upscale-b.pth", "Upscaler B"),
        )
    )
    controller = _model_choice_controller(catalog)
    parent = SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={})

    def build_choice(
        *,
        node_type: str,
        key: str,
        options: list[str],
    ) -> object:
        """Build one standard Comfy combo from its reported option inventory."""

        return factories.build_widget_for_field_behavior(
            parent=parent,
            field_behavior=FieldBehavior(field_key=key),
            node_name="models",
            key=key,
            value=options[0],
            field_meta={},
            prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
            prompt_wildcard_catalog_gateway=_wildcard_gateway(),
            model_choice_snapshot_controller=controller,
            field_type="LIST",
            node_type=node_type,
            field_info=[options, {}],
        )

    fields = {
        "diffusion_model": build_choice(
            node_type="SimpleSyrup.SimpleLoadAnima",
            key="diffusion_model",
            options=[
                "Anima\\anima-a.safetensors",
                "Anima\\anima-b.safetensors",
            ],
        ),
        "diffusion_weight_dtype": build_choice(
            node_type="SimpleSyrup.SimpleLoadAnima",
            key="diffusion_weight_dtype",
            options=["default", "fp8_e4m3fn", "fp8_e5m2"],
        ),
        "text_encoder": build_choice(
            node_type="SimpleSyrup.SimpleLoadAnima",
            key="text_encoder",
            options=[
                "auto",
                "qwen\\encoder-a.safetensors",
                "qwen\\encoder-b.safetensors",
            ],
        ),
        "text_encoder_device": build_choice(
            node_type="SimpleSyrup.SimpleLoadAnima",
            key="text_encoder_device",
            options=["default", "cpu"],
        ),
        "vae": build_choice(
            node_type="SimpleSyrup.SimpleLoadAnima",
            key="vae",
            options=[
                "auto",
                "ClearVAE.safetensors",
                "qwen\\qwen-image-vae.safetensors",
            ],
        ),
        "control_net_name": build_choice(
            node_type="ControlNetLoader",
            key="control_net_name",
            options=["control-a.safetensors", "control-b.safetensors"],
        ),
        "upscale_model_name": build_choice(
            node_type="UpscaleModelLoader",
            key="model_name",
            options=["upscale-a.pth", "upscale-b.pth"],
        ),
        "mixed_allowed_models": build_choice(
            node_type="CustomSelector",
            key="asset",
            options=[
                "Anima\\anima-a.safetensors",
                "Anima\\anima-b.safetensors",
                "ClearVAE.safetensors",
                "qwen\\qwen-image-vae.safetensors",
            ],
        ),
    }

    assert isinstance(fields["diffusion_model"], _FakeModelPickerField)
    assert fields["diffusion_model"].resolution.matched_kinds == ("diffusion_models",)
    assert isinstance(fields["vae"], _FakeModelPickerField)
    assert fields["vae"].resolution.matched_kinds == ("vae",)
    for field_key in (
        "diffusion_weight_dtype",
        "text_encoder",
        "text_encoder_device",
        "control_net_name",
        "upscale_model_name",
        "mixed_allowed_models",
    ):
        assert isinstance(fields[field_key], _FakeComboBox), field_key


def test_build_widget_for_field_behavior_keeps_non_model_lists_as_combo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-model LIST values should still fall back to the plain combo factory."""

    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)
    catalog = _FakeModelCatalog(
        (_model_item("checkpoints", "model-a.safetensors", "Model A"),)
    )
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent=SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={}),
        field_behavior=FieldBehavior(field_key="method"),
        node_name="vectorscopecc",
        key="method",
        value="Straight",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="VectorscopeCC",
        field_info=[["Straight", "Cross", "Ones"], {}],
    )

    assert isinstance(widget, _FakeComboBox)
    assert widget.current_text == "Straight"
    assert widget.max_hint_width == choice_factory._EDITOR_COMBO_MAX_HINT_WIDTH
