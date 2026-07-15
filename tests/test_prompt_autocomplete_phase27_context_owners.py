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

"""Contract tests for Phase 27.5 autocomplete context owners."""

from __future__ import annotations

from collections.abc import Callable, Hashable

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor import (
    PromptAutocompleteQuery,
    PromptScheduledLora,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAutocompleteTriggerWordResult as AsyncTriggerWordResult,
    scheduled_lora_signature,
)
from substitute.presentation.editor.prompt_editor.async_work.scheduled_lora_dispatcher import (
    PromptScheduledLoraCachedContextSnapshot,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteSceneContextController,
    PromptAutocompleteScheduledLoraContextController,
    PromptFeatureSnapshotIdentity,
)


class _SceneIdentityProvider:
    """Publish a deterministic scene identity for scene-context tests."""

    @property
    def scene_context_identity(self) -> PromptFeatureSnapshotIdentity:
        """Return the current scene feature identity."""

        return PromptFeatureSnapshotIdentity(
            source_revision=12,
            scene_context_id=("scene", "portrait"),
            cube_context_id=("cube", "alpha"),
        )


class _ScheduledCurrentContext:
    """Expose live source/query identity to scheduled-LoRA context tests."""

    def __init__(self) -> None:
        """Initialize deterministic live context state."""

        self.source_identity = PromptCommandSourceIdentity(
            source_revision=8,
            source_length=3,
        )
        self.query_identity: Hashable | None = ("tag", "mid")
        self.refresh_calls = 0

    def current_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the live source identity."""

        return self.source_identity

    def current_query_identity(self) -> Hashable | None:
        """Return the live query identity."""

        return self.query_identity

    def refresh_current_query(self) -> None:
        """Record one scheduled-LoRA publication refresh."""

        self.refresh_calls += 1


class _ScheduledContextProvider:
    """Record scheduled-LoRA context owner calls without resolving async work."""

    def __init__(self) -> None:
        """Initialize provider call storage."""

        self.prewarm_calls: list[str] = []
        self.trigger_source_identity: PromptCommandSourceIdentity | None = None
        self.trigger_current_source_identity: PromptCommandSourceIdentity | None = None
        self.trigger_current_source_text: Callable[[], str] | None = None
        self.scheduled_lora = PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Friendly Midna",
            trained_words=("midna helmet",),
            source="inline_prompt",
        )

    def prewarm(self, prompt_text: str) -> bool:
        """Record one prewarm request."""

        self.prewarm_calls.append(prompt_text)
        return True

    def cached_scheduled_loras(
        self,
        prompt_text: str,
    ) -> tuple[PromptScheduledLora, ...] | None:
        """Return cached scheduled LoRAs for one prompt."""

        if prompt_text != "mid":
            return None
        return (self.scheduled_lora,)

    def cached_context_snapshot(
        self,
        prompt_text: str,
    ) -> PromptScheduledLoraCachedContextSnapshot | None:
        """Return cached scheduled-LoRA identity for one prompt."""

        loras = self.cached_scheduled_loras(prompt_text)
        if loras is None:
            return None
        return PromptScheduledLoraCachedContextSnapshot(
            cache_key=("test", prompt_text),
            prompt_context_token=("test", len(prompt_text), hash(prompt_text)),
            scheduled_loras=loras,
            signature=scheduled_lora_signature(loras),
        )

    def trigger_word_result(
        self,
        *,
        prefix: str,
        prompt_text: str,
        source_text: str,
        source_identity: PromptCommandSourceIdentity | None,
        query_identity: Hashable | None,
        current_source_text: Callable[[], str] | None,
        current_query_identity: Callable[[], Hashable | None],
        refresh_current_query: Callable[[], None],
        current_source_identity: Callable[[], PromptCommandSourceIdentity | None]
        | None = None,
    ) -> AsyncTriggerWordResult:
        """Return deterministic trigger rows and record stale-safety callbacks."""

        _ = (prefix, prompt_text, source_text, query_identity)
        self.trigger_source_identity = source_identity
        self.trigger_current_source_text = current_source_text
        self.trigger_current_source_identity = (
            None if current_source_identity is None else current_source_identity()
        )
        assert current_query_identity() == ("tag", "mid")
        refresh_current_query()
        return AsyncTriggerWordResult(
            suggestions=(
                PromptAutocompleteSuggestion(
                    "midna helmet",
                    popularity=None,
                    source_label="Friendly Midna",
                    source_kind="lora_trigger",
                ),
            ),
            scheduled_lora_signature=scheduled_lora_signature((self.scheduled_lora,)),
        )


def test_phase27_scene_context_owner_prepares_effective_prompt_text_and_identity() -> (
    None
):
    """Scene context owner should prepare result context from source snapshots."""

    source = "<lora:global:1>\n**portrait\n<lora:portrait:1>\nmid\n**cafe\nmid"
    portrait_mid = source.index("mid")
    cafe_mid = source.rindex("mid")
    controller = PromptAutocompleteSceneContextController(
        scene_context_provider=_SceneIdentityProvider(),
    )
    feature_identity = PromptFeatureSnapshotIdentity(feature_profile_id=("profile", 1))
    source_identity = PromptCommandSourceIdentity(
        source_revision=4,
        source_length=len(source),
    )

    portrait_context = controller.context_for_tag_query(
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=portrait_mid,
            word_end=portrait_mid + 3,
            active_tag_end=portrait_mid + 3,
        ),
        source_text=source,
        source_identity=source_identity,
        feature_profile_identity=feature_identity,
        query_identity=("tag", "portrait"),
    )
    cafe_context = controller.context_for_tag_query(
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=cafe_mid,
            word_end=cafe_mid + 3,
            active_tag_end=cafe_mid + 3,
        ),
        source_text=source,
        source_identity=source_identity,
        feature_profile_identity=feature_identity,
        query_identity=("tag", "cafe"),
    )

    assert "<lora:portrait:1>" in portrait_context.effective_prompt_text
    assert "<lora:portrait:1>" not in cafe_context.effective_prompt_text
    assert portrait_context.tag_context.source_text == source
    assert portrait_context.tag_context.effective_prompt_text == (
        portrait_context.effective_prompt_text
    )
    assert portrait_context.identity.source_revision == 4
    assert portrait_context.identity.feature_profile_id == ("profile", 1)
    assert portrait_context.identity.scene_context_id == ("scene", "portrait")
    assert portrait_context.identity.cube_context_id == ("cube", "alpha")
    assert (
        portrait_context.identity.query_identity != cafe_context.identity.query_identity
    )


def test_phase27_scheduled_lora_context_owner_delegates_prepared_stale_context() -> (
    None
):
    """Scheduled-LoRA context owner should delegate without owning resolver work."""

    provider = _ScheduledContextProvider()
    current_context = _ScheduledCurrentContext()
    controller = PromptAutocompleteScheduledLoraContextController(
        context_provider=provider,
        current_context=current_context,
        enabled=True,
    )

    result = controller.trigger_word_suggestions(
        "mid",
        "mid",
        source_text="mid",
        source_identity=current_context.source_identity,
        query_identity=("tag", "mid"),
    )

    assert [suggestion.tag for suggestion in result.suggestions] == ["midna helmet"]
    assert provider.trigger_source_identity == current_context.source_identity
    assert provider.trigger_current_source_identity == current_context.source_identity
    assert provider.trigger_current_source_text is None
    assert current_context.refresh_calls == 1


def test_phase27_scheduled_lora_context_owner_fails_closed_when_disabled() -> None:
    """Disabled scheduled-LoRA context should not touch provider work."""

    provider = _ScheduledContextProvider()
    current_context = _ScheduledCurrentContext()
    controller = PromptAutocompleteScheduledLoraContextController(
        context_provider=provider,
        current_context=current_context,
        enabled=False,
    )

    result = controller.trigger_word_suggestions(
        "mid",
        "mid",
        source_text="mid",
        source_identity=current_context.source_identity,
        query_identity=("tag", "mid"),
    )

    assert result.suggestions == ()
    assert result.scheduled_lora_signature == ()
    assert provider.prewarm_calls == []
    assert provider.trigger_source_identity is None
