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

"""Delegate semantic refresh host behavior to a constructed controller."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncResultIdentity,
    PromptSemanticRefreshRequest,
)


class DeferredSemanticRefreshHost:
    """Delegate semantic refresh callbacks to a test controller after construction."""

    def __init__(self, controller_provider: Callable[[], Any]) -> None:
        """Store the provider used to resolve the constructed test controller."""

        self._controller_provider = controller_provider

    def current_semantic_source_text(self) -> str:
        """Return the editor source text that semantic refresh must match."""

        return cast(str, self._controller_provider().current_semantic_source_text())

    def current_semantic_document_source_text(self) -> str:
        """Return the source text represented by the current semantic snapshot."""

        return cast(
            str,
            self._controller_provider().current_semantic_document_source_text(),
        )

    def current_semantic_is_current(self) -> bool:
        """Return whether semantic identity matches the live source."""

        return bool(self._controller_provider().current_semantic_is_current())

    def rebase_current_semantic_source_identity(self) -> bool:
        """Republish exact same-text semantics under the live source identity."""

        return bool(
            self._controller_provider().rebase_current_semantic_source_identity()
        )

    def current_semantic_async_identity(
        self,
        *,
        request_id: int,
    ) -> PromptAsyncResultIdentity:
        """Return current editor identity for one semantic refresh request."""

        return cast(
            PromptAsyncResultIdentity,
            self._controller_provider().current_semantic_async_identity(
                request_id=request_id
            ),
        )

    def apply_fresh_semantic_refresh(
        self,
        request: PromptSemanticRefreshRequest,
    ) -> None:
        """Adopt one semantic request after freshness checks pass."""

        self._controller_provider().apply_fresh_semantic_refresh(request)
