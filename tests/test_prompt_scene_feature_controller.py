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

"""Contracts for direct prompt-scene publication and preparation owners."""

from __future__ import annotations

from pathlib import Path

from substitute.application.prompt_editor.autocomplete.queries import (
    PromptSceneAutocompleteQuery,
)
from substitute.application.prompt_editor.document.semantics import (
    OrdinaryPromptDocumentSemantics,
)
from substitute.application.prompt_editor.scenes.projection import (
    clear_prompt_scene_projection_cache,
)
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureProfileController,
    PromptSceneContextPublication,
    PromptScenePositionContextPreparation,
)
from substitute.presentation.editor.prompt_editor.features.scene_suggestions import (
    scene_autocomplete_suggestions,
)


class _SceneSource:
    """Provide observable source queries to the Qt-free scene owners."""

    def __init__(self, text: str, *, source_revision: int | None = 7) -> None:
        """Store deterministic source state."""

        self.text = text
        self.source_revision = source_revision
        self.read_count = 0

    def source_text(self) -> str:
        """Return prompt source and record one explicit source read."""

        self.read_count += 1
        return self.text

    def source_identity(self) -> PromptSourceIdentity | None:
        """Return source freshness without reading prompt text."""

        if self.source_revision is None:
            return None
        return PromptSourceIdentity(
            source_revision=self.source_revision,
            source_length=len(self.text),
        )


def _owners(
    text: str,
) -> tuple[
    PromptSceneContextPublication, PromptScenePositionContextPreparation, _SceneSource
]:
    """Build direct scene owners with all optional features enabled."""

    source = _SceneSource(text)
    feature_profile = PromptFeatureProfileController(
        PromptEditorFeatureProfile.enabled_profile(())
    )
    document_semantics = OrdinaryPromptDocumentSemantics()
    publication = PromptSceneContextPublication(
        source_identity=source.source_identity,
        feature_profile=feature_profile,
        document_semantics=document_semantics,
    )
    preparation = PromptScenePositionContextPreparation(
        source_text=source.source_text,
        source_identity=source.source_identity,
        publication=publication,
        document_semantics=document_semantics,
    )
    return publication, preparation, source


def test_scene_publication_carries_titles_and_context_identity() -> None:
    """Publication should own workflow identity and autocomplete title state."""

    publication, _, _ = _owners("quality")
    publication.set_context_identity(
        cube_context_id=("cube", "node", "positive"),
        scene_context_id=("workflow", "scene-table"),
    )
    publication.set_scene_autocomplete_titles(("Portrait", "Cafe"))

    snapshot = publication.snapshot
    assert snapshot.identity.source_revision == 7
    assert snapshot.identity.cube_context_id == ("cube", "node", "positive")
    assert snapshot.identity.scene_context_id == ("workflow", "scene-table")
    assert snapshot.autocomplete.titles == ("Portrait", "Cafe")
    assert snapshot.autocomplete.ready is True


def test_scene_suggestions_consume_immutable_publication_state() -> None:
    """Pure scene suggestion policy should dedupe and exclude exact no-op rows."""

    publication, _, _ = _owners("**Cafe")
    publication.set_scene_autocomplete_titles(
        ("Cafe", "Cafe Interior", "cafe interior", "Canal")
    )

    suggestions = scene_autocomplete_suggestions(
        state=publication.snapshot.autocomplete,
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


def test_scene_suggestions_are_disabled_without_prepared_scene_titles() -> None:
    """Pure policy should fail closed when scene publication is not ready."""

    publication, _, _ = _owners("quality")
    suggestions = scene_autocomplete_suggestions(
        state=publication.snapshot.autocomplete,
        query=PromptSceneAutocompleteQuery(
            prefix="Cafe",
            marker_start=0,
            title_start=2,
            cursor_position=6,
            replacement_end=6,
        ),
        limit=10,
    )

    assert suggestions == ()


def test_position_preparation_resolves_queueable_scene_and_effective_context() -> None:
    """Preparation should materialize queue context and publish its action state."""

    clear_prompt_scene_projection_cache()
    source = "quality\n<lora:global:1>\n**Portrait\nportrait text\n**Cafe\ncafe text"
    publication, preparation, _ = _owners(source)
    publication.set_queueable_scene_keys(frozenset({"portrait", "cafe"}))

    context = preparation.position_context(source.index("cafe text"))

    assert context.scene_key == "cafe"
    assert context.queueable_scene_key == "cafe"
    assert context.effective_prompt_text == "quality\n<lora:global:1>\n\ncafe text"
    assert publication.snapshot.queue_action.action_ready is True
    assert publication.snapshot.queue_action.scene_key == "cafe"


def test_position_preparation_enumerates_unique_effective_scene_prompts() -> None:
    """Source lifecycle consumers should receive every effective prompt once."""

    clear_prompt_scene_projection_cache()
    source = "quality\n**Portrait\nportrait text\n**Cafe\ncafe text"
    _, preparation, _ = _owners(source)

    effective_prompts = preparation.effective_prompt_texts()

    assert "quality\n\nportrait text" in effective_prompts
    assert "quality\n\ncafe text" in effective_prompts
    assert len(effective_prompts) == len(set(effective_prompts))


def test_position_preparation_omits_unqueueable_scene_actions() -> None:
    """Prepared contexts should not publish actions for unavailable scene keys."""

    source = "quality\n**Portrait\nportrait text\n**Cafe\ncafe text"
    publication, preparation, _ = _owners(source)
    publication.set_queueable_scene_keys(frozenset({"cafe"}))

    context = preparation.position_context(source.index("portrait text"))

    assert context.scene_key == "portrait"
    assert context.queueable_scene_key is None
    assert context.effective_prompt_text == "quality\n\nportrait text"
    assert publication.snapshot.queue_action.action_ready is False
    assert publication.snapshot.queue_action.scene_key is None


def test_prepared_position_context_is_menu_safe_after_prepare() -> None:
    """Prepared reads must not touch source after explicit preparation."""

    clear_prompt_scene_projection_cache()
    source_text = "quality\n**Portrait\nportrait text"
    publication, preparation, source = _owners(source_text)
    publication.set_queueable_scene_keys(frozenset({"portrait"}))

    prepared = preparation.prepare_position_context(
        source_text.index("portrait text"),
        reason="test_pre_menu_prepare",
    )
    reads_after_prepare = source.read_count
    menu_snapshot = preparation.prepared_position_context(
        source_text.index("portrait text")
    )

    assert prepared.ready is True
    assert menu_snapshot.context is not None
    assert menu_snapshot.context.queueable_scene_key == "portrait"
    assert source.read_count == reads_after_prepare


def test_prepared_position_context_fails_closed_without_preparation() -> None:
    """Menu-safe reads should not derive scene state on demand."""

    _, preparation, source = _owners("quality\n**Portrait\nportrait text")

    snapshot = preparation.prepared_position_context(0)

    assert snapshot.ready is False
    assert snapshot.stale is True
    assert snapshot.context is None
    assert snapshot.unavailable_reason == "scene_position_context_unprepared"
    assert source.read_count == 0


def test_queue_key_publication_invalidates_prepared_position_context() -> None:
    """Queue-key identity changes should make prior prepared state unavailable."""

    source_text = "quality\n**Portrait\nportrait text"
    publication, preparation, _ = _owners(source_text)
    publication.set_queueable_scene_keys(frozenset({"portrait"}))
    source_position = source_text.index("portrait text")

    prepared = preparation.prepare_position_context(
        source_position,
        reason="test_pre_menu_prepare",
    )
    publication.set_queueable_scene_keys(frozenset())
    unavailable = preparation.prepared_position_context(source_position)

    assert prepared.context is not None
    assert prepared.context.queueable_scene_key == "portrait"
    assert unavailable.ready is False
    assert unavailable.stale is True
    assert unavailable.unavailable_reason == "scene_position_context_unprepared"


def test_prepared_position_context_requires_source_identity() -> None:
    """Prepared reads should not fall back to prompt text when identity is absent."""

    source_text = "quality\n**Portrait\nportrait text"
    publication, preparation, source = _owners(source_text)
    source.source_revision = None
    _ = publication

    snapshot = preparation.prepared_position_context(0)

    assert snapshot.ready is False
    assert snapshot.stale is True
    assert snapshot.context is None
    assert snapshot.unavailable_reason == "source_revision_unavailable"
    assert source.read_count == 0


def test_scene_owners_replace_the_deleted_controller_without_qt_dependencies() -> None:
    """Scene publication and preparation must remain direct, Qt-free authorities."""

    feature_root = (
        Path(__file__).parents[1]
        / "substitute"
        / "presentation"
        / "editor"
        / "prompt_editor"
        / "features"
    )
    publication_source = (feature_root / "scene_publication.py").read_text(
        encoding="utf-8"
    )
    preparation_source = (feature_root / "scene_position_context.py").read_text(
        encoding="utf-8"
    )

    assert not (feature_root / "scene_controller.py").exists()
    assert "PromptSceneFeatureController" not in publication_source
    assert "PromptSceneFeatureController" not in preparation_source
    assert "PySide6" not in publication_source
    assert "PySide6" not in preparation_source
    assert "toPlainText" not in publication_source
