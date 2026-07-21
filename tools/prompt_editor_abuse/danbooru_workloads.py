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

"""Define deterministic Danbooru import and wiki-menu abuse workloads."""

from __future__ import annotations

from substitute.devtools.prompt_editor_performance.scenarios import (
    DANBOORU_IMPORT_URL,
)

from .models import PromptAbuseAction, PromptAbuseScenario


def danbooru_scenarios() -> tuple[PromptAbuseScenario, ...]:
    """Return URL import and selected-text wiki preparation scenarios."""

    return (_danbooru_import_scenario(), _danbooru_wiki_scenario())


def _danbooru_import_scenario() -> PromptAbuseScenario:
    """Paste a supported URL through literal insertion and async replacement."""

    imported = "imported_tag, imported_character"
    return PromptAbuseScenario(
        name="danbooru-url-paste-import",
        initial_text="",
        actions=(
            PromptAbuseAction("paste", value=DANBOORU_IMPORT_URL),
            PromptAbuseAction("drain_events", expected_source=imported),
        ),
        expected_text=imported,
        fixture_features=("danbooru_import",),
    )


def _danbooru_wiki_scenario() -> PromptAbuseScenario:
    """Build the selected-text wiki action without opening a native dialog."""

    source = "blue_hair, detailed portrait"
    return PromptAbuseScenario(
        name="danbooru-wiki-selection-menu",
        initial_text=source,
        actions=(
            PromptAbuseAction(
                "select",
                position=0,
                selection_end=len("blue_hair"),
                expected_source=source,
                expected_cursor_position=len("blue_hair"),
                expected_anchor_position=0,
            ),
            PromptAbuseAction(
                "context_menu",
                position=2,
                expected_source=source,
                expected_context_labels=("Danbooru wiki lookup",),
            ),
            PromptAbuseAction("event_turn", expected_source=source),
        ),
        expected_text=source,
        cursor_position=len(source),
        fixture_features=("danbooru_wiki",),
    )


__all__ = ["danbooru_scenarios"]
