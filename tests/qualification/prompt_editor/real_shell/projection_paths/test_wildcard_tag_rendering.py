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

"""Qualify wildcard group-tag reprojection through the production prompt shell."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QFontMetricsF

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.wildcard_renderer import (
    PromptWildcardInlineObjectRenderer,
)
from tests.support.prompt_editor.projection_engine_support import surface_for
from tests.support.prompt_editor.real_shell.models import PromptFieldHandle
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


_CANARY_PREFIX = (
    "**White Dress\n"
    "1girl, ponytail, {haircolor} hair, white dress dress, pout,\n"
    "**Black Dress\n"
    "1girl, ponytail, "
)
_CANARY_INSERTION = "{haircolor} hair, black dress, smug, narrowed eyes,"


def _wildcard_tokens(field: PromptFieldHandle) -> tuple[PromptProjectionToken, ...]:
    """Return wildcard tokens from one mounted prompt field."""

    return tuple(
        token
        for token in surface_for(field.editor).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.WILDCARD
    )


def test_adding_second_wildcard_remeasures_first_implicit_group_tag(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Remeasure the first wildcard when a later occurrence gives it a `1` tag."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text=_CANARY_PREFIX
    )
    surface = surface_for(field.editor)
    renderer = PromptWildcardInlineObjectRenderer()
    before_token = _wildcard_tokens(field)[0]
    before_rect = surface._layout.frame.geometry.tokens.token_rect(  # noqa: SLF001
        before_token,
        scroll_offset=float(field.editor.verticalScrollBar().value()),
    )

    assert before_token.wildcard_display_tag is None
    assert before_rect is not None

    real_shell_scenario.input.type_text(field, _CANARY_INSERTION)

    after_tokens = _wildcard_tokens(field)
    first_token = after_tokens[0]
    after_rect = surface._layout.frame.geometry.tokens.token_rect(  # noqa: SLF001
        first_token,
        scroll_offset=float(field.editor.verticalScrollBar().value()),
    )
    expected_tag_width = QFontMetricsF(
        renderer._tag_font(field.editor.font())  # noqa: SLF001
    ).horizontalAdvance("1")

    assert field.editor.toPlainText() == _CANARY_PREFIX + _CANARY_INSERTION
    assert tuple(token.wildcard_display_tag for token in after_tokens) == ("1", "1")
    assert after_rect is not None
    assert after_rect.width() > before_rect.width()
    assert after_rect.width() - before_rect.width() == pytest.approx(
        expected_tag_width,
        abs=1.0,
    )


def test_numeric_wildcard_tag_owns_its_weight_hit_rectangle(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Find the tag's numeric hit area after its separate opening decoration."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="{animal|2}")
    surface = surface_for(field.editor)
    token = _wildcard_tokens(field)[0]

    anchor_rect = surface.token_anchor_rect(token)
    weight_rect = surface.token_weight_text_rect(token)

    assert anchor_rect is not None
    assert weight_rect == anchor_rect
