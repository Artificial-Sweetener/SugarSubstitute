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

"""Tests for startup editor cache warmup coordination."""

from __future__ import annotations

from tests.execution_testing import ImmediateTaskSubmitter
from substitute.app.bootstrap.editor_startup_warmup import (
    BackendEditorStartupWarmupHandle,
    DEFAULT_EDITOR_WARMUP_NODE_CLASSES,
    LocalEditorStartupWarmupHandle,
)


class _CloseRecorder:
    """Record warmup submitter route closure."""

    def __init__(self) -> None:
        """Initialize close tracking."""

        self.calls = 0

    def close(self) -> None:
        """Record one close request."""

        self.calls += 1


class _Resolver:
    """Record model-choice warmup calls."""

    def __init__(self) -> None:
        """Initialize call tracking."""

        self.prewarm_calls: list[tuple[tuple[str, ...], ...]] = []

    def prewarm(self, option_lists: tuple[tuple[str, ...], ...] = ()) -> int:
        """Record option-list warmup and return a count."""

        normalized = tuple(tuple(options) for options in option_lists)
        self.prewarm_calls.append(normalized)
        return len(normalized)

    def cached_resolution_count(self) -> int:
        """Return a deterministic cached resolution count."""

        return 0


class _NodeDefinitionGateway:
    """Record node-definition prewarm requests."""

    def __init__(self) -> None:
        """Initialize call tracking."""

        self.calls: list[tuple[str, ...]] = []

    def prewarm_node_classes(self, node_classes: tuple[str, ...]) -> int:
        """Record node class names requested for startup warmup."""

        self.calls.append(tuple(node_classes))
        return len(node_classes)


class _PromptAutocompleteGateway:
    """Record prompt autocomplete warmup calls."""

    def __init__(self) -> None:
        """Initialize call tracking."""

        self.warm_calls = 0

    def warm(self) -> None:
        """Record one autocomplete warmup."""

        self.warm_calls += 1


class _PromptWildcardGateway:
    """Record wildcard catalog warmup calls."""

    def __init__(self) -> None:
        """Initialize call tracking."""

        self.search_calls: list[tuple[str, int]] = []

    def search_wildcards(self, prefix: str, limit: int = 10) -> tuple[object, ...]:
        """Record one wildcard search warmup."""

        self.search_calls.append((prefix, limit))
        return (object(),)


class _PromptLoraCatalog:
    """Record prompt LoRA catalog warmup calls."""

    def __init__(self, cached: tuple[object, ...] | None = None) -> None:
        """Initialize call tracking."""

        self.cached = cached
        self.cached_calls = 0
        self.list_calls = 0

    def cached_loras(self) -> tuple[object, ...] | None:
        """Record one non-loading cache read."""

        self.cached_calls += 1
        return self.cached

    def list_loras(self) -> tuple[object, ...]:
        """Record one LoRA catalog warmup."""

        self.list_calls += 1
        return (object(), object())


class _SpellcheckSnapshot:
    """Expose spellcheck issues for warmup tests."""

    issues: tuple[object, ...] = ()


class _PromptSpellcheckService:
    """Record prompt spellcheck warmup calls."""

    def __init__(self) -> None:
        """Initialize call tracking."""

        self.snapshot_calls: list[str] = []

    def snapshot_for_text(self, text: str) -> _SpellcheckSnapshot:
        """Record one spellcheck snapshot warmup."""

        self.snapshot_calls.append(text)
        return _SpellcheckSnapshot()


def test_local_editor_warmup_prepares_backend_independent_caches() -> None:
    """Local warmup should prepare editor caches without node-definition calls."""

    gateway = _NodeDefinitionGateway()
    autocomplete = _PromptAutocompleteGateway()
    wildcards = _PromptWildcardGateway()
    loras = _PromptLoraCatalog()
    spellcheck = _PromptSpellcheckService()
    close_recorder = _CloseRecorder()
    handle = LocalEditorStartupWarmupHandle(
        prompt_autocomplete_gateway=autocomplete,
        prompt_wildcard_catalog_gateway=wildcards,
        prompt_lora_catalog_service=loras,
        prompt_spellcheck_service=spellcheck,
        submitter=ImmediateTaskSubmitter(),
        close_submitter=close_recorder.close,
    )

    handle.start()
    handle.start()
    handle.shutdown()

    assert gateway.calls == []
    assert autocomplete.warm_calls == 1
    assert wildcards.search_calls == [("", 1)]
    assert loras.cached_calls == 1
    assert loras.list_calls == 1
    assert spellcheck.snapshot_calls == ["warmup prompt"]
    assert close_recorder.calls == 1


def test_local_editor_warmup_uses_cached_loras_without_listing() -> None:
    """Local warmup should not force backend LoRA listing when cache exists."""

    loras = _PromptLoraCatalog(cached=(object(),))
    handle = LocalEditorStartupWarmupHandle(
        prompt_lora_catalog_service=loras,
        submitter=ImmediateTaskSubmitter(),
    )

    handle.start()

    assert loras.cached_calls == 1
    assert loras.list_calls == 0


def test_backend_editor_warmup_prewarms_node_definitions() -> None:
    """Backend warmup should isolate Comfy node-definition cache preparation."""

    gateway = _NodeDefinitionGateway()
    resolver = _Resolver()
    close_recorder = _CloseRecorder()
    handle = BackendEditorStartupWarmupHandle(
        node_definition_gateway=gateway,
        model_choice_resolver=resolver,
        submitter=ImmediateTaskSubmitter(),
        close_submitter=close_recorder.close,
    )

    handle.start()
    handle.start()
    handle.shutdown()

    assert gateway.calls == [DEFAULT_EDITOR_WARMUP_NODE_CLASSES]
    assert resolver.prewarm_calls == [()]
    assert close_recorder.calls == 1
