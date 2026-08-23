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

"""Boundary tests for prompt autocomplete module ownership."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_retired_autocomplete_surface_module_is_not_importable() -> None:
    """The retired autocomplete surface module should not remain as a shim."""

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(
            "substitute.presentation.editor.prompt_editor.autocomplete_surface"
        )


def test_popularity_formatting_helper_uses_thousands_separators() -> None:
    """Autocomplete popularity formatting remains human-readable and exact."""

    mod = importlib.import_module(
        "substitute.presentation.editor.prompt_editor.overlays.autocomplete_panel"
    )

    assert mod.format_prompt_autocomplete_popularity(5_889_398) == "5,889,398"


def test_popularity_formatting_helper_hides_zero_values() -> None:
    """Zero popularity renders as an empty secondary label."""

    mod = importlib.import_module(
        "substitute.presentation.editor.prompt_editor.overlays.autocomplete_panel"
    )

    assert mod.format_prompt_autocomplete_popularity(0) == ""


def test_prompt_editor_module_no_longer_parses_category_or_raw_autocomplete_rows() -> (
    None
):
    """PromptEditor should not keep category/raw-line parsing helpers."""

    mod = importlib.import_module("substitute.presentation.editor.prompt_editor.widget")
    module_file = mod.__file__
    assert module_file is not None
    source = Path(module_file).read_text(encoding="utf-8")

    assert not hasattr(mod, "parse_popularity_value")
    assert "raw_line" not in source
