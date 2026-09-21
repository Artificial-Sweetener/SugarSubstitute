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

"""Tests for source-line, search, and scene-diagnostic publication owners."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.projection.scene_diagnostics_owner import (
    PromptSceneDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.projection.search_presentation_owner import (
    PromptSearchPresentationOwner,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from substitute.presentation.editor.prompt_editor.projection.source_line_chrome import (
    PromptSourceLineChrome,
)
from substitute.presentation.editor.prompt_editor.projection.source_line_presentation_owner import (
    PromptSourceLinePresentationOwner,
)


@dataclass(slots=True)
class _Effects:
    """Record ordered publication effects exposed to presentation owners."""

    events: list[str]

    def record(self, event: str) -> None:
        """Append one publication event."""

        self.events.append(event)


def test_scene_diagnostics_publish_changed_keys_as_one_rebuild_transaction() -> None:
    """Changed scene diagnostics should flush, clear hover, and rebuild once."""

    effects = _Effects([])
    owner = PromptSceneDiagnosticsOwner(
        flush_pending_projection=lambda reason: effects.record(f"flush:{reason}"),
        clear_hovered_token=lambda: effects.record("clear_hover"),
        rebuild_projection=lambda: effects.record("rebuild"),
    )

    owner.set_keys(frozenset({"scene-1"}))
    owner.set_keys(frozenset({"scene-1"}))

    assert owner.keys == frozenset({"scene-1"})
    assert effects.events == [
        "flush:set_scene_error_keys",
        "clear_hover",
        "rebuild",
    ]


def test_search_presentation_publishes_session_state_before_render_effects() -> None:
    """Search transitions should update authoritative session state before painting."""

    session = PromptProjectionSession()
    observed: list[tuple[str, tuple[tuple[int, int], ...]]] = []
    owner = PromptSearchPresentationOwner(
        session=session,
        publish_changed=lambda: observed.append(
            ("changed", session.search_match_ranges)
        ),
        publish_cleared=lambda: observed.append(
            ("cleared", session.search_match_ranges)
        ),
        request_update=lambda: observed.append(("update", session.search_match_ranges)),
    )

    owner.set_matches(((2, 4),), active_index=0)
    owner.clear_matches()

    assert observed == [
        ("changed", ((2, 4),)),
        ("update", ((2, 4),)),
        ("cleared", ()),
        ("update", ()),
    ]


def test_source_line_inset_flushes_before_layout_publication() -> None:
    """A changed source-line inset should publish geometry in deterministic order."""

    effects = _Effects([])
    chrome = PromptSourceLineChrome()
    owner = PromptSourceLinePresentationOwner(
        chrome=chrome,
        flush_pending_projection=lambda reason: effects.record(f"flush:{reason}"),
        synchronize_layout=lambda: effects.record("sync_layout"),
        publish_configuration_changed=lambda: effects.record("config_changed"),
        request_update=lambda: effects.record("update"),
    )

    owner.set_content_left_inset(24.0)
    owner.set_content_left_inset(24.0)
    owner.set_enabled(True)

    assert chrome.content_left_inset == 24.0
    assert chrome.enabled is True
    assert effects.events == [
        "flush:set_source_line_content_left_inset",
        "sync_layout",
        "update",
        "config_changed",
        "update",
    ]
