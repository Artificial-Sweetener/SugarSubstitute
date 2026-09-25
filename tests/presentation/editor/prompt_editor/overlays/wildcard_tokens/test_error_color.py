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

"""Verify wildcard resolution is visible in decorated brace color."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QWidget

from substitute.application.ports import PromptWildcardResolution
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.wildcard_renderer import (
    PromptWildcardInlineObjectRenderer,
)
from substitute.presentation.semantic_colors import semantic_error_color
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
    show_prompt_editor,
    surface_for,
)
from tests.support.qt.lifecycle import destroy_widget_roots


def test_missing_wildcard_braces_use_error_color_only_after_resolution() -> None:
    """Distinguish an unresolved wildcard from a provisional edited identity."""

    widgets: list[QWidget] = []
    try:
        box = show_prompt_editor(
            widgets,
            text="{missing|2}",
            width=240,
            wildcard_gateway=StaticPromptWildcardCatalogGateway({}),
        )
        token = next(
            token
            for token in surface_for(box).projection_document().tokens
            if token.kind is PromptProjectionTokenKind.WILDCARD
        )
        renderer = PromptWildcardInlineObjectRenderer()

        assert token.exists is False
        assert token.wildcard_resolution_pending is False
        assert (
            renderer._accent_color_for_token(  # noqa: SLF001
                token,
                palette=box.palette(),
            ).rgba()
            == semantic_error_color().rgba()
        )
        assert (
            renderer._accent_color_for_token(  # noqa: SLF001
                replace(token, wildcard_resolution_pending=True),
                palette=box.palette(),
            ).rgba()
            == box.palette().color(QPalette.ColorRole.Text).rgba()
        )

        valid_box = show_prompt_editor(
            widgets,
            text="{color|2}",
            width=240,
            wildcard_gateway=StaticPromptWildcardCatalogGateway(
                {
                    ("color", "simple", None): PromptWildcardResolution(
                        identifier="color",
                        wildcard_form="simple",
                        csv_column=None,
                        exists=True,
                    )
                }
            ),
        )
        valid_token = next(
            token
            for token in surface_for(valid_box).projection_document().tokens
            if token.kind is PromptProjectionTokenKind.WILDCARD
        )
        assert valid_token.exists is True
        assert (
            renderer._accent_color_for_token(  # noqa: SLF001
                valid_token,
                palette=valid_box.palette(),
            ).rgba()
            != semantic_error_color().rgba()
        )
    finally:
        destroy_widget_roots(widgets)
