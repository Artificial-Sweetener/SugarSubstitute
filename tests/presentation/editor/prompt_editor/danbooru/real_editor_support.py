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

"""Provide deterministic real-editor Danbooru paste-import collaborators."""

from __future__ import annotations

from typing import Any, cast

from substitute.application.danbooru import (
    DanbooruPromptImportResult,
    DanbooruUrlClassification,
    DanbooruUrlImportService,
)
from substitute.presentation.editor.prompt_editor import PromptEditor


class StaticDanbooruUrlImportService:
    """Return deterministic Danbooru URL import outcomes for widget tests."""

    def __init__(
        self,
        *,
        classification: DanbooruUrlClassification | None,
        result: DanbooruPromptImportResult,
    ) -> None:
        """Store deterministic classification and import outcomes."""

        self._classification = classification
        self._result = result
        self.classify_calls: list[str] = []
        self.import_calls: list[str] = []

    def classify_url(self, text: str) -> DanbooruUrlClassification | None:
        """Return the configured URL classification for pasted text."""

        self.classify_calls.append(text)
        return self._classification

    def import_prompt_from_url(self, text: str) -> DanbooruPromptImportResult:
        """Return the configured import result for pasted text."""

        self.import_calls.append(text)
        return self._result


class FailingDanbooruUrlImportService(StaticDanbooruUrlImportService):
    """Raise a deterministic import failure for safe-logging contracts."""

    def __init__(self, *, classification: DanbooruUrlClassification) -> None:
        """Store the classification used before the synthetic failure."""

        super().__init__(
            classification=classification,
            result=DanbooruPromptImportResult(imported_prompt=None),
        )

    def import_prompt_from_url(self, text: str) -> DanbooruPromptImportResult:
        """Raise an error that includes content which logging must not expose."""

        self.import_calls.append(text)
        raise RuntimeError(text)


class ImmediateDanbooruImportDispatcher:
    """Run paste lookups inline for deterministic real-widget contracts."""

    def submit(
        self,
        lookup: Any,
        *,
        completed: Any,
        failed: Any,
    ) -> None:
        """Execute lookup and route either its result or failure."""

        try:
            completed(lookup())
        except BaseException as error:  # noqa: BLE001
            failed(error)


def configure_danbooru_url_import(
    editor: PromptEditor,
    service: object,
    *,
    dispatcher: ImmediateDanbooruImportDispatcher,
) -> None:
    """Configure Danbooru paste/import through the composed editor controller."""

    cast(Any, editor)._danbooru_paste_import_controller.configure_danbooru_url_import(
        cast(DanbooruUrlImportService, service),
        enabled=True,
        dispatcher=dispatcher,
    )
