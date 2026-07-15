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
    FieldValueSource,
    extract_live_list_default,
    extract_live_list_options,
    resolve_live_list_value,
)


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
