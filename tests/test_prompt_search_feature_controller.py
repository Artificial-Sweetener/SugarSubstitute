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

"""Tests for prompt search feature controller ownership."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor import PromptEditorFeatureProfile
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureProfileController,
    PromptSearchFeatureController,
)


class _SearchHost:
    """Provide source identity for search feature controller tests."""

    def __init__(self, source_revision: int = 4) -> None:
        """Store the source revision returned to the controller."""

        self._source_revision = source_revision

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return a deterministic source identity."""

        return PromptCommandSourceIdentity(source_revision=self._source_revision)


@dataclass(slots=True)
class _SearchSurface:
    """Record projected search highlight publication."""

    matches: tuple[tuple[int, int], ...] = ()
    active_index: int | None = None
    clear_calls: int = 0

    def set_search_matches(
        self,
        matches: tuple[tuple[int, int], ...],
        *,
        active_index: int | None,
    ) -> None:
        """Record painted search ranges."""

        self.matches = matches
        self.active_index = active_index

    def clear_search_matches(self) -> None:
        """Record search highlight clearing."""

        self.matches = ()
        self.active_index = None
        self.clear_calls += 1


def _controller(
    surface: _SearchSurface,
    *,
    source_revision: int = 4,
) -> PromptSearchFeatureController:
    """Build a search controller with deterministic feature state."""

    return PromptSearchFeatureController(
        host=_SearchHost(source_revision),
        surface=surface,
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(())
        ),
    )


def test_search_controller_publishes_source_revision_bound_snapshot() -> None:
    """Search highlights should carry source revision and query identity."""

    surface = _SearchSurface()
    controller = _controller(surface, source_revision=9)

    snapshot = controller.set_search_matches(
        ((0, 5), (11, 5)),
        active_index=1,
        query_identity=("text", "alpha"),
    )

    assert snapshot.identity.source_revision == 9
    assert snapshot.identity.query_identity == ("text", "alpha")
    assert snapshot.highlights.match_ranges == ((0, 5), (11, 5))
    assert snapshot.highlights.active_index == 1
    assert snapshot.projection_ready is True
    assert surface.matches == ((0, 5), (11, 5))
    assert surface.active_index == 1


def test_search_controller_clears_snapshot_and_projection_state() -> None:
    """Clearing search should clear both prepared and projected state."""

    surface = _SearchSurface()
    controller = _controller(surface)
    controller.set_search_matches(
        ((0, 5),),
        active_index=0,
        query_identity=("text", "alpha"),
    )

    snapshot = controller.clear_search_matches()

    assert snapshot.highlights.match_ranges == ()
    assert snapshot.highlights.active_index is None
    assert snapshot.identity.query_identity is None
    assert surface.matches == ()
    assert surface.active_index is None
    assert surface.clear_calls == 1
