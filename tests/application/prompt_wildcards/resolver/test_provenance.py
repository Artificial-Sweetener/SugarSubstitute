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

"""Verify prompt wildcard resolution provenance."""

from __future__ import annotations

from substitute.application.prompt_wildcards.resolver import PromptWildcardResolver
from substitute.application.prompt_wildcards import PromptWildcardResolutionContext
from substitute.domain.prompt.wildcards.models import PromptWildcardTextSource


class _SourceProvider:
    """Return one deterministic prompt wildcard source."""

    def load_text_source(self, identifier: str) -> PromptWildcardTextSource | None:
        """Return a fixed simple wildcard source."""

        if identifier == "animal":
            return PromptWildcardTextSource(
                source_id="animal",
                lines=("wolf", "bear", "fox"),
            )
        return None

    def load_csv_source(self, identifier: str) -> None:
        """Return no CSV source."""

        _ = identifier
        return None


def test_resolver_records_wildcard_replacement_provenance() -> None:
    """Wildcard resolution should retain selected source metadata for tracing."""

    resolver = PromptWildcardResolver(_SourceProvider())

    resolution = resolver.resolve(
        "A {animal}",
        seed=1,
        context=PromptWildcardResolutionContext(),
    )

    assert resolution.replacements == (("{animal}", "wolf"),)
    assert len(resolution.replacement_details) == 1
    detail = resolution.replacement_details[0]
    assert detail.outer_text == "{animal}"
    assert detail.value == "wolf"
    assert detail.identifier == "animal"
    assert detail.source_id == "animal"
    assert detail.selected_index == 0
    assert detail.line_number == 1
    assert detail.item_count == 3
    assert detail.seed == 1
