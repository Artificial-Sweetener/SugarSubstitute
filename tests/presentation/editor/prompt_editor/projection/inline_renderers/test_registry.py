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

"""Inline projection renderer registry contracts."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.projection.emphasis_renderer import (
    PromptEmphasisPrefixRenderer,
    PromptEmphasisSuffixRenderer,
)
from substitute.presentation.editor.prompt_editor.projection.lora_renderer import (
    PromptLoraInlineObjectRenderer,
)
from substitute.presentation.editor.prompt_editor.projection.inline_renderer_registry import (
    PromptProjectionInlineObjectRendererRegistry,
)
from substitute.presentation.editor.prompt_editor.projection.wildcard_renderer import (
    PromptWildcardInlineObjectRenderer,
)


def test_registry_resolves_each_renderer_by_its_stable_projection_key() -> None:
    """The layout renderer keys should resolve to the configured renderer instances."""

    renderers = (
        PromptEmphasisPrefixRenderer(),
        PromptEmphasisSuffixRenderer(),
        PromptLoraInlineObjectRenderer(),
        PromptWildcardInlineObjectRenderer(),
    )
    registry = PromptProjectionInlineObjectRendererRegistry(renderers)

    assert tuple(renderer.renderer_key for renderer in renderers) == (
        "emphasis_prefix",
        "emphasis_suffix",
        "lora_chip",
        "wildcard_chip",
    )
    for renderer in renderers:
        assert registry.renderer_for(renderer.renderer_key) is renderer


def test_registry_rejects_absent_keys_and_preserves_registration_precedence() -> None:
    """Unknown keys should miss while duplicate keys retain first-owner precedence."""

    first = PromptEmphasisPrefixRenderer()
    duplicate = PromptEmphasisPrefixRenderer()
    registry = PromptProjectionInlineObjectRendererRegistry((first, duplicate))

    assert registry.renderer_for(None) is None
    assert registry.renderer_for("unknown") is None
    assert registry.renderer_for(first.renderer_key) is first
