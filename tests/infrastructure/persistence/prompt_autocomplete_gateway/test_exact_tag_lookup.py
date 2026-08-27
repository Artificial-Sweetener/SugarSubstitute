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

"""Verify exact tag lookup through the file autocomplete gateway."""

from substitute.infrastructure.persistence.file_prompt_autocomplete_gateway import (
    FilePromptAutocompleteGateway,
)


def test_file_prompt_autocomplete_gateway_supports_exact_tag_lookup() -> None:
    """Answer exact tag membership for normalized prompt-tag spellcheck queries."""

    gateway = FilePromptAutocompleteGateway()

    assert gateway.contains_prompt_tag("looking_at_viewer") is True
    assert gateway.contains_prompt_tag("looking at viewer") is True
    assert gateway.contains_prompt_tag("looking at view") is False
