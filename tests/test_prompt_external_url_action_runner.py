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

"""Tests for prompt-editor external URL action execution."""

from __future__ import annotations

from collections.abc import Callable

from substitute.presentation.editor.prompt_editor.interactions import (
    PromptExternalUrlActionRunner,
    PromptExternalUrlOpenRequest,
)


def test_external_url_runner_opens_prepared_request_with_injected_opener() -> None:
    """Runner should delegate prepared requests to the injected opener."""

    opened_urls: list[str] = []
    runner = PromptExternalUrlActionRunner(_recording_opener(opened_urls))

    assert runner.open_external_url_request(
        PromptExternalUrlOpenRequest(
            action_id="test.open",
            url="https://example.invalid/path",
        )
    )

    assert opened_urls == ["https://example.invalid/path"]


def test_external_url_runner_preserves_failed_open_result() -> None:
    """Runner should preserve the opener's failure result."""

    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record the URL and report failure."""

        opened_urls.append(url)
        return False

    runner = PromptExternalUrlActionRunner(open_url)

    assert not runner.open_civitai_model_page("https://civitai.example/models/1")
    assert opened_urls == ["https://civitai.example/models/1"]


def test_external_url_runner_routes_civitai_and_danbooru_actions() -> None:
    """Runner should expose explicit feature action entrypoints."""

    opened_urls: list[str] = []
    runner = PromptExternalUrlActionRunner(_recording_opener(opened_urls))

    assert runner.open_civitai_model_page("https://civitai.example/models/2")
    assert runner.open_danbooru_external_url("https://danbooru.example/wiki_pages/tag")

    assert opened_urls == [
        "https://civitai.example/models/2",
        "https://danbooru.example/wiki_pages/tag",
    ]


def _recording_opener(opened_urls: list[str]) -> Callable[[str], bool]:
    """Return a successful opener that records URLs."""

    def open_url(url: str) -> bool:
        """Record the URL and report success."""

        opened_urls.append(url)
        return True

    return open_url
