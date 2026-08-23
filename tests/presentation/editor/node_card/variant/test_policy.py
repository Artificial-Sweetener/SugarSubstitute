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

"""Tests for node-card variant resolution and composition policy."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.editor.panel.node_card.variant import (
    NodeCardVariant,
    column_span_for_node_card_variant,
    resolve_node_card_variant,
    style_for_node_card_variant,
)


def _behavior_with_card_mode(value: str) -> SimpleNamespace:
    """Return a minimal resolved-behavior double with one card-mode value."""

    return SimpleNamespace(card=SimpleNamespace(card_mode=SimpleNamespace(value=value)))


def test_prompt_card_mode_resolves_prompt_editor_variant() -> None:
    """Prompt card mode should map to the prompt-editor variant."""

    variant = resolve_node_card_variant(_behavior_with_card_mode("prompt"))

    assert variant is NodeCardVariant.PROMPT_EDITOR
    assert column_span_for_node_card_variant(variant) == 2
    assert style_for_node_card_variant(variant).prompt_editor is True


def test_non_prompt_card_mode_uses_standard_variant() -> None:
    """Non-prompt card modes should keep the standard card variant by default."""

    variant = resolve_node_card_variant(_behavior_with_card_mode("field"))

    assert variant is NodeCardVariant.STANDARD
    assert column_span_for_node_card_variant(variant) == 1
    assert style_for_node_card_variant(variant).prompt_editor is False
