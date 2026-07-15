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

"""Own prepared LoRA action snapshots for foreground menu consumers."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass

from substitute.application.prompt_editor import PromptScheduledLora

from ..async_work.scheduled_lora_dispatcher import (
    PromptScheduledLoraCachedContextSnapshot,
    scheduled_lora_signature,
)
from ..commands import PromptCommandSourceIdentity, PromptFeatureSnapshotIdentity
from .catalog_snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from .lora_context_menu import (
    PromptLoraContextActionController,
    PromptLoraTokenContext,
    PromptLoraTriggerWordsAction,
)


@dataclass(frozen=True, slots=True)
class PromptLoraActionSnapshot:
    """Publish prepared LoRA actions with source, catalog, and context identity."""

    identity: CatalogSnapshotIdentity
    status: CatalogSnapshotStatus
    trigger_word_actions: tuple[PromptLoraTriggerWordsAction, ...]

    @property
    def consumable(self) -> bool:
        """Return whether foreground code may present actions from this snapshot."""

        return self.status.consumable


class PromptLoraTriggerWordProjector:
    """Project trigger-word actions from authoritative LoRA snapshots."""

    def __init__(
        self,
        *,
        context_actions: PromptLoraContextActionController,
        source_identity_provider: Callable[[], PromptCommandSourceIdentity | None],
        feature_profile_id_provider: Callable[[], Hashable | None],
        catalog_revision_provider: Callable[[], Hashable | None],
        trigger_words_enabled: Callable[[], bool],
    ) -> None:
        """Store pure action collaborators and identity providers."""

        self._context_actions = context_actions
        self._source_identity_provider = source_identity_provider
        self._feature_profile_id_provider = feature_profile_id_provider
        self._catalog_revision_provider = catalog_revision_provider
        self._trigger_words_enabled = trigger_words_enabled

    def snapshot_for_prompt(
        self,
        *,
        prompt_text: str,
        cached_context: PromptScheduledLoraCachedContextSnapshot | None,
    ) -> PromptLoraActionSnapshot:
        """Return prepared trigger-word actions for one scheduled-LoRA context."""

        if not self._trigger_words_enabled():
            return self._empty_snapshot(
                prompt_context_token=self._prompt_context_token(
                    prompt_text,
                    context_token="lora_trigger_words_disabled",
                ),
                readiness=CatalogSnapshotReadiness.DISABLED,
                unavailable_reason="trigger_words_disabled",
            )
        if cached_context is None:
            return self._empty_snapshot(
                prompt_context_token=self._prompt_context_token(
                    prompt_text,
                    context_token="lora_trigger_words_cold",
                ),
                readiness=CatalogSnapshotReadiness.COLD,
                unavailable_reason=None,
            )
        if not self._cached_context_matches_prompt(
            cached_context,
            prompt_text=prompt_text,
        ):
            return self._empty_snapshot(
                prompt_context_token=cached_context.prompt_context_token,
                readiness=CatalogSnapshotReadiness.UNAVAILABLE,
                unavailable_reason="stale_scheduled_lora_context",
                request_identity=cached_context.signature,
                stale=True,
            )
        identity = self._catalog_identity(
            prompt_context_token=cached_context.prompt_context_token,
            request_identity=cached_context.signature,
            query_identity=("lora_trigger_words", cached_context.prompt_context_token),
            stale=False,
        )
        feature_identity = self._feature_identity(identity)
        return PromptLoraActionSnapshot(
            identity=identity,
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            trigger_word_actions=tuple(
                action
                for scheduled_lora in self._context_actions.loras_with_configured_trigger_words(
                    cached_context.scheduled_loras
                )
                if (
                    action := self._context_actions.trigger_words_action_for_lora(
                        scheduled_lora,
                        identity=feature_identity,
                        snapshot_identity=identity,
                    )
                )
                is not None
            ),
        )

    def unavailable_snapshot_for_prompt(
        self,
        *,
        prompt_text: str,
        unavailable_reason: str,
    ) -> PromptLoraActionSnapshot:
        """Return an unavailable trigger-word snapshot without deriving actions."""

        return self._empty_snapshot(
            prompt_context_token=self._prompt_context_token(
                prompt_text,
                context_token=unavailable_reason,
            ),
            readiness=CatalogSnapshotReadiness.UNAVAILABLE,
            unavailable_reason=unavailable_reason,
            stale=True,
        )

    def trigger_words_action_for_lora(
        self,
        scheduled_lora: PromptScheduledLora,
        *,
        prompt_text: str,
    ) -> PromptLoraTriggerWordsAction | None:
        """Return a prepared trigger-word action for one known LoRA row."""

        if not self._trigger_words_enabled():
            return None
        request_identity = scheduled_lora_signature((scheduled_lora,))
        identity = self._catalog_identity(
            prompt_context_token=self._prompt_context_token(
                prompt_text,
                context_token=("direct_lora", scheduled_lora.backend_value),
            ),
            request_identity=request_identity,
            query_identity=("lora_trigger_words", request_identity),
            stale=False,
        )
        return self._context_actions.trigger_words_action_for_lora(
            scheduled_lora,
            identity=self._feature_identity(identity),
            snapshot_identity=identity,
        )

    def trigger_words_action_for_token(
        self,
        token_context: PromptLoraTokenContext,
        *,
        prompt_text: str,
    ) -> PromptLoraTriggerWordsAction | None:
        """Return a prepared trigger-word action for one projected LoRA token."""

        if not self._trigger_words_enabled():
            return None
        identity = self._catalog_identity(
            prompt_context_token=self._prompt_context_token(
                prompt_text,
                context_token=("inline_lora", token_context.backend_value),
            ),
            request_identity=(
                "inline_lora",
                token_context.backend_value,
                token_context.trained_words,
            ),
            query_identity=("lora_trigger_words", token_context.backend_value),
            stale=False,
        )
        return self._context_actions.trigger_words_action_for_token(
            token_context,
            identity=self._feature_identity(identity),
            snapshot_identity=identity,
        )

    def _empty_snapshot(
        self,
        *,
        prompt_context_token: Hashable,
        readiness: CatalogSnapshotReadiness,
        unavailable_reason: str | None,
        request_identity: Hashable | None = None,
        stale: bool = False,
    ) -> PromptLoraActionSnapshot:
        """Return an empty LoRA action snapshot for non-ready states."""

        identity = self._catalog_identity(
            prompt_context_token=prompt_context_token,
            request_identity=request_identity,
            query_identity=("lora_trigger_words", prompt_context_token),
            stale=stale,
            unavailable_reason=unavailable_reason,
        )
        return PromptLoraActionSnapshot(
            identity=identity,
            status=CatalogSnapshotStatus(
                readiness,
                unavailable_reason=unavailable_reason,
            ),
            trigger_word_actions=(),
        )

    def _catalog_identity(
        self,
        *,
        prompt_context_token: Hashable | None,
        request_identity: Hashable | None,
        query_identity: Hashable | None,
        stale: bool,
        unavailable_reason: str | None = None,
    ) -> CatalogSnapshotIdentity:
        """Return freshness identity for prepared LoRA action state."""

        source_identity = self._source_identity_provider()
        return CatalogSnapshotIdentity(
            source_revision=(
                None if source_identity is None else source_identity.source_revision
            ),
            feature_profile_id=self._feature_profile_id_provider(),
            catalog_revision=self._catalog_revision_provider(),
            prompt_context_token=prompt_context_token,
            query_identity=query_identity,
            request_identity=request_identity,
            stale=stale,
            unavailable_reason=unavailable_reason,
        )

    @staticmethod
    def _feature_identity(
        identity: CatalogSnapshotIdentity,
    ) -> PromptFeatureSnapshotIdentity:
        """Adapt catalog action identity to the shared command identity shape."""

        return PromptFeatureSnapshotIdentity(
            source_revision=identity.source_revision,
            feature_profile_id=identity.feature_profile_id,
            catalog_revision=identity.catalog_revision,
            stale=identity.stale,
            query_identity=(
                "lora_action",
                identity.catalog_revision,
                identity.prompt_context_token,
                identity.request_identity,
            ),
        )

    @staticmethod
    def _cached_context_matches_prompt(
        cached_context: PromptScheduledLoraCachedContextSnapshot,
        *,
        prompt_text: str,
    ) -> bool:
        """Return whether cached scheduled-LoRA rows match the prompt request."""

        return cached_context.cache_key[1] == prompt_text

    @staticmethod
    def _prompt_context_token(
        prompt_text: str,
        *,
        context_token: Hashable,
    ) -> tuple[Hashable, int, int]:
        """Return a prompt-safe action context token without storing prompt text."""

        return (context_token, len(prompt_text), hash(prompt_text))


__all__ = [
    "PromptLoraActionSnapshot",
    "PromptLoraTriggerWordProjector",
]
