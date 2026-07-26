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

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

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
    PromptProjectionLayoutSnapshot,
)

from .tokens import (
    PromptProjectionInlineObjectRendererRegistry,
    PromptRichInlineObjectRenderer,
)


@dataclass(frozen=True, slots=True)
class PromptProjectionInlinePaintBinding:
    """Contain resolved collaborators for one inline layout fragment."""

    renderer: PromptRichInlineObjectRenderer
    run: PromptProjectionRun
    token: PromptProjectionToken


class PromptProjectionBaseInlineBindings:
    """Own immutable base bindings and affected-fragment indexes."""

    def __init__(
        self,
        bindings: Mapping[int, PromptProjectionInlinePaintBinding],
        *,
        fragment_ids_by_run_id: Mapping[str, tuple[int, ...]],
        fragment_ids_by_token_id: Mapping[str, tuple[int, ...]],
    ) -> None:
        """Retain exact fragment bindings behind read-only mappings."""

        self._bindings = MappingProxyType(dict(bindings))
        self._fragment_ids_by_run_id = MappingProxyType(dict(fragment_ids_by_run_id))
        self._fragment_ids_by_token_id = MappingProxyType(
            dict(fragment_ids_by_token_id)
        )

    def binding(
        self,
        fragment: PromptProjectionInlineObjectFragment,
    ) -> PromptProjectionInlinePaintBinding | None:
        """Return the prepared base binding for one fragment."""

        return self._bindings.get(id(fragment))

    def effective_overrides(
        self,
        *,
        runs_by_id: Mapping[str, PromptProjectionRun],
        tokens_by_id: Mapping[str, PromptProjectionToken],
    ) -> Mapping[int, PromptProjectionInlinePaintBinding]:
        """Prepare bindings only for fragments affected by paint-state overrides."""

        affected_ids: set[int] = set()
        for run_id in runs_by_id:
            affected_ids.update(self._fragment_ids_by_run_id.get(run_id, ()))
        for token_id in tokens_by_id:
            affected_ids.update(self._fragment_ids_by_token_id.get(token_id, ()))
        overrides: dict[int, PromptProjectionInlinePaintBinding] = {}
        for fragment_id in affected_ids:
            base = self._bindings.get(fragment_id)
            if base is None:
                continue
            overrides[fragment_id] = PromptProjectionInlinePaintBinding(
                renderer=base.renderer,
                run=runs_by_id.get(base.run.run_id, base.run),
                token=tokens_by_id.get(base.token.token_id, base.token),
            )
        return MappingProxyType(overrides)


def prepare_base_inline_bindings(
    projection_document: PromptProjectionDocument,
    layout_snapshot: PromptProjectionLayoutSnapshot,
    *,
    renderers: PromptProjectionInlineObjectRendererRegistry,
) -> PromptProjectionBaseInlineBindings:
    """Resolve inline fragment collaborators during geometry publication."""

    bindings: dict[int, PromptProjectionInlinePaintBinding] = {}
    fragment_ids_by_run_id: defaultdict[str, list[int]] = defaultdict(list)
    fragment_ids_by_token_id: defaultdict[str, list[int]] = defaultdict(list)
    for line in layout_snapshot.lines:
        for fragment in line.fragments:
            if not isinstance(fragment, PromptProjectionInlineObjectFragment):
                continue
            run = projection_document.run_by_id(fragment.run_id)
            token = projection_document.token_by_id(fragment.token_id)
            renderer = renderers.renderer_for(fragment.renderer_key)
            if run is None or token is None or renderer is None:
                continue
            fragment_id = id(fragment)
            bindings[fragment_id] = PromptProjectionInlinePaintBinding(
                renderer=renderer,
                run=run,
                token=token,
            )
            fragment_ids_by_run_id[run.run_id].append(fragment_id)
            fragment_ids_by_token_id[token.token_id].append(fragment_id)
    return PromptProjectionBaseInlineBindings(
        bindings,
        fragment_ids_by_run_id={
            run_id: tuple(fragment_ids)
            for run_id, fragment_ids in fragment_ids_by_run_id.items()
        },
        fragment_ids_by_token_id={
            token_id: tuple(fragment_ids)
            for token_id, fragment_ids in fragment_ids_by_token_id.items()
        },
    )


__all__ = [
    "PromptProjectionBaseInlineBindings",
    "PromptProjectionInlinePaintBinding",
    "prepare_base_inline_bindings",
]
