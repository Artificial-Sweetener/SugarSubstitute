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

"""Run prepared prompt-editor external URL actions through one boundary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.presentation.widgets.civitai_page_action import open_external_url

PromptExternalUrlOpener = Callable[[str], bool]


@dataclass(frozen=True, slots=True)
class PromptExternalUrlOpenRequest:
    """Describe one prepared external URL open request."""

    action_id: str
    url: str


class PromptExternalUrlActionRunner:
    """Delegate prompt-editor external URL actions to the configured opener."""

    def __init__(
        self,
        open_url: PromptExternalUrlOpener | None = None,
    ) -> None:
        """Store the opener while preserving the default desktop behavior."""

        self._open_url = open_url or open_external_url

    def open_external_url_request(
        self,
        request: PromptExternalUrlOpenRequest,
    ) -> bool:
        """Open one prepared external URL request and return opener success."""

        return self._open_url(request.url)

    def open_civitai_model_page(self, url: str) -> bool:
        """Open a prepared CivitAI model-page URL."""

        return self.open_external_url_request(
            PromptExternalUrlOpenRequest(
                action_id="lora.open_model_page",
                url=url,
            )
        )

    def open_danbooru_external_url(self, url: str) -> bool:
        """Open a prepared Danbooru dialog external URL."""

        return self.open_external_url_request(
            PromptExternalUrlOpenRequest(
                action_id="danbooru.open_external_url",
                url=url,
            )
        )
