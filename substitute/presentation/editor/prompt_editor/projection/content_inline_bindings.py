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

"""Bind inline layout fragments to prepared render collaborators."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionInlineObjectFragment,
)

from substitute.presentation.editor.prompt_editor.projection.inline_renderer_registry import (
    PromptProjectionInlineObjectRendererRegistry,
)
from substitute.presentation.editor.prompt_editor.projection.inline_renderer import (
    PromptRichInlineObjectRenderer,
)


@dataclass(frozen=True, slots=True)
class PromptProjectionInlinePaintBinding:
    """Contain resolved collaborators for one inline layout fragment."""

    renderer: PromptRichInlineObjectRenderer
    run: PromptProjectionRun
    token: PromptProjectionToken


class PromptProjectionBaseInlineBindings:
    """Resolve and cache inline bindings only for fragments that are consumed."""

    def __init__(
        self,
        projection_document: PromptProjectionDocument,
        *,
        renderers: PromptProjectionInlineObjectRendererRegistry,
    ) -> None:
        """Retain immutable owners without walking the full layout snapshot."""

        self._projection_document = projection_document
        self._renderers = renderers
        self._bindings: dict[int, PromptProjectionInlinePaintBinding] = {}

    def binding(
        self,
        fragment: PromptProjectionInlineObjectFragment,
    ) -> PromptProjectionInlinePaintBinding | None:
        """Return one cached binding, preparing it on first visible use."""

        fragment_id = id(fragment)
        prepared = self._bindings.get(fragment_id)
        if prepared is not None:
            return prepared
        run = self._projection_document.run_by_id(fragment.run_id)
        token = self._projection_document.token_by_id(fragment.token_id)
        renderer = self._renderers.renderer_for(fragment.renderer_key)
        if run is None or token is None or renderer is None:
            return None
        prepared = PromptProjectionInlinePaintBinding(
            renderer=renderer,
            run=run,
            token=token,
        )
        self._bindings[fragment_id] = prepared
        return prepared


def prepare_base_inline_bindings(
    projection_document: PromptProjectionDocument,
    *,
    renderers: PromptProjectionInlineObjectRendererRegistry,
) -> PromptProjectionBaseInlineBindings:
    """Create lazy inline binding ownership for one projection document."""

    return PromptProjectionBaseInlineBindings(
        projection_document,
        renderers=renderers,
    )


__all__ = [
    "PromptProjectionBaseInlineBindings",
    "PromptProjectionInlinePaintBinding",
    "prepare_base_inline_bindings",
]
