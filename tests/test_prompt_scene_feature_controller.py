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

"""Tests for prompt scene feature controller ownership."""

from __future__ import annotations

from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptSceneAutocompleteQuery,
)
from substitute.application.prompt_editor.prompt_scene_projection_service import (
    clear_prompt_scene_projection_cache,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureProfileController,
    PromptSceneFeatureController,
)


class _SceneHost:
    """Provide source text and identity to the scene feature controller."""

    def __init__(self, text: str, *, source_revision: int | None = 7) -> None:
        """Store deterministic source state for controller tests."""

        self._text = text
        self._source_revision = source_revision
        self.read_count = 0

    def toPlainText(self) -> str:
        """Return the configured prompt source."""

        self.read_count += 1
        return self._text

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return a command source identity matching the configured source."""

        if self._source_revision is None:
            return None
        return PromptCommandSourceIdentity(
            source_revision=self._source_revision,
            source_length=len(self._text),
        )


def _controller(text: str) -> PromptSceneFeatureController:
    """Build a scene feature controller with all optional features enabled."""

    return PromptSceneFeatureController(
        host=_SceneHost(text),
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(())
        ),
    )


def test_scene_controller_publishes_titles_and_context_identity() -> None:
    """Scene snapshots should carry source, cube, scene, and title readiness."""

    controller = _controller("quality")

    controller.set_context_identity(
        cube_context_id=("cube", "node", "positive"),
        scene_context_id=("workflow", "scene-table"),
    )
    controller.set_scene_autocomplete_titles(("Portrait", "Cafe"))

    snapshot = controller.snapshot
    assert snapshot.identity.source_revision == 7
    assert snapshot.identity.cube_context_id == ("cube", "node", "positive")
    assert snapshot.identity.scene_context_id == ("workflow", "scene-table")
    assert snapshot.autocomplete.titles == ("Portrait", "Cafe")
    assert snapshot.autocomplete.ready is True


def test_scene_controller_prepares_title_suggestions() -> None:
    """Scene autocomplete suggestions should dedupe and exclude exact no-op matches."""

    controller = _controller("**Cafe")
    controller.set_scene_autocomplete_titles(
        ("Cafe", "Cafe Interior", "cafe interior", "Canal")
    )

    suggestions = controller.scene_autocomplete_suggestions(
        query=PromptSceneAutocompleteQuery(
            prefix="Cafe",
            marker_start=0,
            title_start=2,
            cursor_position=6,
            replacement_end=6,
        ),
        limit=10,
    )

    assert [suggestion.tag for suggestion in suggestions] == ["Cafe Interior"]
    assert all(suggestion.source_kind == "scene" for suggestion in suggestions)


def test_scene_controller_resolves_queueable_scene_and_effective_context() -> None:
    """Scene context should prepare queue action state and materialized prompt text."""

    clear_prompt_scene_projection_cache()
    source = "quality\n<lora:global:1>\n**Portrait\nportrait text\n**Cafe\ncafe text"
    controller = _controller(source)
    controller.set_queueable_scene_keys(frozenset({"portrait", "cafe"}))

    context = controller.position_context(source.index("cafe text"))

    assert context.scene_key == "cafe"
    assert context.queueable_scene_key == "cafe"
    assert context.effective_prompt_text == "quality\n<lora:global:1>\n\ncafe text"
    assert controller.snapshot.queue_action.action_ready is True
    assert controller.snapshot.queue_action.scene_key == "cafe"


def test_scene_controller_enumerates_unique_effective_scene_prompts() -> None:
    """Source lifecycle owners should receive every effective scene prompt once."""

    clear_prompt_scene_projection_cache()
    source = "quality\n**Portrait\nportrait text\n**Cafe\ncafe text"
    controller = _controller(source)

    effective_prompts = controller.effective_prompt_texts()

    assert "quality\n\nportrait text" in effective_prompts
    assert "quality\n\ncafe text" in effective_prompts
    assert len(effective_prompts) == len(set(effective_prompts))


def test_scene_controller_omits_unqueueable_scene_actions() -> None:
    """Scene queue action state should stay unavailable for unqueueable scenes."""

    source = "quality\n**Portrait\nportrait text\n**Cafe\ncafe text"
    controller = _controller(source)
    controller.set_queueable_scene_keys(frozenset({"cafe"}))

    context = controller.position_context(source.index("portrait text"))

    assert context.scene_key == "portrait"
    assert context.queueable_scene_key is None
    assert context.effective_prompt_text == "quality\n\nportrait text"
    assert controller.snapshot.queue_action.action_ready is False
    assert controller.snapshot.queue_action.scene_key is None


def test_scene_controller_prepared_position_context_is_menu_safe_after_prepare() -> (
    None
):
    """Prepared scene-position reads should not touch source text on menu open."""

    clear_prompt_scene_projection_cache()
    source = "quality\n**Portrait\nportrait text"
    host = _SceneHost(source)
    controller = PromptSceneFeatureController(
        host=host,
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(())
        ),
    )
    controller.set_queueable_scene_keys(frozenset({"portrait"}))

    prepared = controller.prepare_position_context(
        source.index("portrait text"),
        reason="test_pre_menu_prepare",
    )
    read_count_after_prepare = host.read_count
    menu_snapshot = controller.prepared_position_context(source.index("portrait text"))

    assert prepared.ready is True
    assert menu_snapshot.context is not None
    assert menu_snapshot.context.queueable_scene_key == "portrait"
    assert host.read_count == read_count_after_prepare


def test_scene_controller_prepared_position_context_reports_unprepared_without_computing() -> (
    None
):
    """Prepared scene-position reads should fail closed when no snapshot exists."""

    host = _SceneHost("quality\n**Portrait\nportrait text")
    controller = PromptSceneFeatureController(
        host=host,
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(())
        ),
    )

    snapshot = controller.prepared_position_context(0)

    assert snapshot.ready is False
    assert snapshot.stale is True
    assert snapshot.context is None
    assert snapshot.unavailable_reason == "scene_position_context_unprepared"
    assert host.read_count == 0


def test_scene_controller_invalidates_prepared_position_when_queueable_keys_change() -> (
    None
):
    """Queueable-scene changes should make old prepared position contexts stale."""

    source = "quality\n**Portrait\nportrait text"
    controller = _controller(source)
    controller.set_queueable_scene_keys(frozenset({"portrait"}))
    source_position = source.index("portrait text")

    prepared = controller.prepare_position_context(
        source_position,
        reason="test_pre_menu_prepare",
    )
    controller.set_queueable_scene_keys(frozenset())
    unavailable = controller.prepared_position_context(source_position)

    assert prepared.context is not None
    assert prepared.context.queueable_scene_key == "portrait"
    assert unavailable.ready is False
    assert unavailable.stale is True
    assert unavailable.unavailable_reason == "scene_position_context_unprepared"


def test_scene_controller_prepared_position_requires_source_identity() -> None:
    """Menu-safe scene-position reads should not fall back to source text identity."""

    host = _SceneHost("quality\n**Portrait\nportrait text", source_revision=None)
    controller = PromptSceneFeatureController(
        host=host,
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(())
        ),
    )

    snapshot = controller.prepared_position_context(0)

    assert snapshot.ready is False
    assert snapshot.stale is True
    assert snapshot.context is None
    assert snapshot.unavailable_reason == "source_revision_unavailable"
    assert host.read_count == 0
