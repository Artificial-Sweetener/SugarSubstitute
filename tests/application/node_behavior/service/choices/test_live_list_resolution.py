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

"""Contract tests for application-owned live list value resolution."""

from __future__ import annotations

from substitute.application.node_behavior import (
    ChoiceAvailability,
    FieldValueSource,
    choice_inventory,
    extract_live_list_default,
    extract_live_list_options,
    has_authoritative_picker_options,
    is_blank_picker_value,
    resolve_picker_fallback,
    resolve_choice_inventory_for_field,
    resolve_live_list_value,
)


def test_choice_inventory_distinguishes_missing_empty_and_populated_metadata() -> None:
    """Finite-choice availability must not infer empty state from missing metadata."""

    missing = choice_inventory(["COMBO", {}])
    empty = choice_inventory(["COMBO", {"options": []}])
    populated = choice_inventory(["COMBO", {"options": ["auto"]}])

    assert missing.availability is ChoiceAvailability.UNAVAILABLE
    assert missing.authoritative is False
    assert empty.availability is ChoiceAvailability.EMPTY
    assert empty.authoritative is True
    assert populated.availability is ChoiceAvailability.POPULATED
    assert populated.string_options == ("auto",)


def test_live_empty_choice_inventory_overrides_stale_prepared_options() -> None:
    """An authoritative live empty list must not fall back to stale cube metadata."""

    class Gateway:
        """Return one live empty Comfy field definition."""

        def get_node_definition(self, node_class: str) -> dict[str, object]:
            """Return cached object-info for the requested node class."""

            return {
                node_class: {
                    "input": {
                        "required": {
                            "model_name": ["COMBO", {"options": []}],
                        }
                    }
                }
            }

        def get_required_node_definition(self, node_class: str) -> dict[str, object]:
            """Return the same object-info through the required gateway method."""

            return self.get_node_definition(node_class)

    inventory = resolve_choice_inventory_for_field(
        key="model_name",
        node_type="UpscaleModelLoader",
        node_definition_gateway=Gateway(),
        field_info=["COMBO", {"options": ["stale.pth"]}],
    )

    assert inventory.availability is ChoiceAvailability.EMPTY
    assert inventory.options == ()


def test_resolve_live_list_value_keeps_explicit_valid_literal() -> None:
    """Valid explicit literals should win over all fallback sources."""

    resolution = resolve_live_list_value(
        raw_value="model-b",
        field_info=[["model-a", "model-b"], {"default": "model-a"}],
        remembered_value="model-a",
    )

    assert resolution is not None
    assert resolution.effective_value == "model-b"
    assert resolution.value_source == FieldValueSource.EXPLICIT
    assert resolution.should_canonicalize is False


def test_resolve_live_list_value_falls_back_to_live_default() -> None:
    """Invalid literals should fall back to the live Comfy default when available."""

    resolution = resolve_live_list_value(
        raw_value="stale-model",
        field_info=[["model-a", "model-b"], {"default": "model-b"}],
        remembered_value=None,
    )

    assert resolution is not None
    assert resolution.effective_value == "model-b"
    assert resolution.value_source == FieldValueSource.LIVE_DEFAULT
    assert resolution.should_canonicalize is True
    assert resolution.canonical_value == "model-b"


def test_resolve_live_list_value_falls_back_to_first_option_without_default() -> None:
    """Invalid literals should use the first live option when no default exists."""

    resolution = resolve_live_list_value(
        raw_value="stale-model",
        field_info=[["model-a", "model-b"], {}],
        remembered_value=None,
    )

    assert resolution is not None
    assert resolution.effective_value == "model-a"
    assert resolution.value_source == FieldValueSource.FIRST_OPTION
    assert resolution.should_canonicalize is True
    assert resolution.canonical_value == "model-a"


def test_resolve_live_list_value_keeps_future_remembered_default_slot() -> None:
    """Remembered user defaults should outrank live defaults when implemented later."""

    resolution = resolve_live_list_value(
        raw_value="stale-model",
        field_info=[["model-a", "model-b"], {"default": "model-a"}],
        remembered_value="model-b",
    )

    assert resolution is not None
    assert resolution.effective_value == "model-b"
    assert resolution.value_source == FieldValueSource.FUTURE_USER_DEFAULT
    assert resolution.should_canonicalize is True
    assert resolution.canonical_value == "model-b"


def test_resolve_live_list_value_returns_none_without_live_options() -> None:
    """Missing live options should leave the caller to handle the unresolved field."""

    assert (
        resolve_live_list_value(
            raw_value="anything",
            field_info=None,
            remembered_value=None,
        )
        is None
    )


def test_extract_live_list_options_reads_combo_metadata_options() -> None:
    """COMBO fields expose their choices through the metadata options key."""

    assert extract_live_list_options(
        [
            "COMBO",
            {
                "options": [
                    "ESRGAN_4x.pth",
                    "R-ESRGAN 4x+ Anime6B.pth",
                ]
            },
        ]
    ) == ("ESRGAN_4x.pth", "R-ESRGAN 4x+ Anime6B.pth")


def test_extract_live_list_options_ignores_invalid_combo_metadata() -> None:
    """Invalid COMBO metadata should behave like a choice field without options."""

    assert extract_live_list_options(["COMBO", {"options": "not-a-list"}]) == ()


def test_extract_live_list_default_reads_combo_metadata_default() -> None:
    """COMBO defaults should use the same metadata slot as LIST defaults."""

    assert (
        extract_live_list_default(["COMBO", {"default": "b", "options": ["a", "b"]}])
        == "b"
    )


def test_resolve_live_list_value_keeps_explicit_valid_combo_literal() -> None:
    """Valid COMBO literals should follow the same precedence as LIST values."""

    resolution = resolve_live_list_value(
        raw_value="R-ESRGAN 4x+ Anime6B.pth",
        field_info=[
            "COMBO",
            {
                "options": [
                    "ESRGAN_4x.pth",
                    "R-ESRGAN 4x+ Anime6B.pth",
                ]
            },
        ],
        remembered_value=None,
    )

    assert resolution is not None
    assert resolution.effective_value == "R-ESRGAN 4x+ Anime6B.pth"
    assert resolution.value_source == FieldValueSource.EXPLICIT
    assert resolution.should_canonicalize is False


def test_resolve_live_list_value_falls_back_for_combo_metadata() -> None:
    """Invalid COMBO values should fall back through default then first option."""

    default_resolution = resolve_live_list_value(
        raw_value="missing.pth",
        field_info=["COMBO", {"default": "b.pth", "options": ["a.pth", "b.pth"]}],
        remembered_value=None,
    )
    first_option_resolution = resolve_live_list_value(
        raw_value="missing.pth",
        field_info=["COMBO", {"options": ["a.pth", "b.pth"]}],
        remembered_value=None,
    )

    assert default_resolution is not None
    assert default_resolution.effective_value == "b.pth"
    assert default_resolution.value_source == FieldValueSource.LIVE_DEFAULT
    assert first_option_resolution is not None
    assert first_option_resolution.effective_value == "a.pth"
    assert first_option_resolution.value_source == FieldValueSource.FIRST_OPTION


def test_resolve_picker_fallback_prefers_valid_comfy_default() -> None:
    """Executable picker fallback should prefer Comfy's declared default."""

    fallback = resolve_picker_fallback(
        [["model-a", "model-b"], {"default": "model-b"}],
        allow_first_option=True,
    )

    assert fallback is not None
    assert fallback.value == "model-b"
    assert fallback.source == "default"


def test_resolve_picker_fallback_uses_sole_option_without_default() -> None:
    """A sole live option should become the executable picker value."""

    fallback = resolve_picker_fallback(
        [["only-model"], {}],
        allow_first_option=True,
    )

    assert fallback is not None
    assert fallback.value == "only-model"
    assert fallback.source == "first_option"


def test_blank_picker_value_recognizes_unset_literals() -> None:
    """Persistence should share one definition of an unset picker value."""

    assert is_blank_picker_value(None) is True
    assert is_blank_picker_value("   ") is True
    assert is_blank_picker_value("model.safetensors") is False


def test_empty_model_options_clear_stale_literal_only_when_authoritative() -> None:
    """An explicit empty Comfy list should clear a stale model selection."""

    resolution = resolve_live_list_value(
        raw_value=r"Flux\missing.safetensors",
        field_info=[[], {}],
        remembered_value=None,
        clear_when_options_empty=True,
    )

    assert resolution is not None
    assert resolution.effective_value == ""
    assert resolution.value_source is FieldValueSource.NO_OPTIONS
    assert resolution.should_canonicalize is True
    assert resolution.canonical_value == ""


def test_missing_model_options_preserve_literal_during_definition_failure() -> None:
    """Missing option metadata should not erase a model during a transient failure."""

    resolution = resolve_live_list_value(
        raw_value=r"Flux\selected.safetensors",
        field_info=None,
        remembered_value=None,
        clear_when_options_empty=True,
    )

    assert resolution is None
    assert has_authoritative_picker_options(None) is False
    assert has_authoritative_picker_options(["COMBO", {}]) is False
    assert has_authoritative_picker_options(["COMBO", {"options": []}]) is True
