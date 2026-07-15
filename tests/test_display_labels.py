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

"""Tests for shared user-facing label formatting."""

from __future__ import annotations

from substitute.application.display_labels import beautify_label


def test_beautify_label_applies_whole_key_overrides() -> None:
    """Whole-key overrides should preserve established editor labels."""

    assert beautify_label("sampler_name") == "Sampler"
    assert beautify_label("scheduler") == "Scheduler"
    assert beautify_label("ksampler") == "KSampler"
    assert beautify_label("cfg") == "CFG"


def test_beautify_label_title_cases_machine_keys() -> None:
    """Machine keys should become human-readable title labels."""

    assert beautify_label("") == ""
    assert beautify_label("text_to_image") == "Text to Image"
    assert beautify_label("image to image") == "Image to Image"


def test_beautify_label_keeps_middle_minor_words_lowercase() -> None:
    """Minor words should stay lowercase unless they are first or last."""

    assert beautify_label("a_walk_in_the_park") == "A Walk in the Park"
    assert beautify_label("before_and_after") == "Before and After"


def test_beautify_label_applies_requested_acronym_tokens() -> None:
    """Requested acronym tokens should normalize independent of input casing."""

    assert beautify_label("Cfg") == "CFG"
    assert beautify_label("Vae") == "VAE"
    assert beautify_label("Lora") == "LoRA"
    assert beautify_label("vae_loader") == "VAE Loader"
    assert beautify_label("lora_name") == "LoRA Name"
    assert beautify_label("cfg_scale") == "CFG Scale"


def test_beautify_label_does_not_add_unrequested_acronyms() -> None:
    """Unapproved acronym-like tokens should use ordinary title casing."""

    assert beautify_label("clip_loader") == "Clip Loader"
    assert beautify_label("sdxl_model") == "Sdxl Model"


def test_beautify_label_preserves_cube_alias_prefix() -> None:
    """Cube alias prefixes should retain authored casing."""

    assert beautify_label("sdxl/Text to Image") == "sdxl/Text to Image"
    assert beautify_label("SDXL/Text to Image") == "SDXL/Text to Image"


def test_beautify_label_formats_cube_alias_body_after_prefix() -> None:
    """Cube alias bodies should use normal label formatting after the prefix."""

    assert beautify_label("SDXL/text_to_image") == "SDXL/Text to Image"
    assert beautify_label("SDXL/vae_loader") == "SDXL/VAE Loader"


def test_beautify_label_treats_boundary_slashes_as_plain_text() -> None:
    """Boundary slashes should not create preserved cube alias prefixes."""

    assert beautify_label("/Text to Image") == "/Text to Image"
    assert beautify_label("SDXL/") == "SDXL/"
