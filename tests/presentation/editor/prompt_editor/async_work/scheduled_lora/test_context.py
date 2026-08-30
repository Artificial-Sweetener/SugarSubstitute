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

"""Baseline Phase 27 autocomplete behavior before SOC extraction."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from typing import Any, cast

import pytest

from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptScheduledLoraContextCoordinator,
)


from tests.presentation.editor.prompt_editor.autocomplete.phase27_support import (
    _ScheduledLoraExecutor,
    _ScheduledLoraResolver,
    _Token,
)


def test_phase27_scheduled_lora_context_warm_cold_stale_failed_and_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Scheduled-LoRA autocomplete context should be cached, async, and stale-safe."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("imp princess", "twilight imp"),
        source="cube_field",
    )
    resolver = _ScheduledLoraResolver((scheduled_lora,))
    executor = _ScheduledLoraExecutor()
    provider = PromptScheduledLoraContextCoordinator(
        resolver=resolver,
        enabled=True,
        executor=cast(Any, executor),
    )
    refresh_calls = 0

    def record_refresh() -> None:
        """Record one visible autocomplete refresh."""

        nonlocal refresh_calls
        refresh_calls += 1

    source_identity = PromptSourceIdentity(source_revision=7, source_length=2)
    cold = provider.trigger_word_result(
        prefix="imp",
        prompt_text="mi",
        source_text="mi",
        source_identity=source_identity,
        query_identity=("tag", 0, 2, 2, 10),
        current_source_text=lambda: "mi",
        current_query_identity=lambda: ("tag", 0, 2, 2, 10),
        refresh_current_query=record_refresh,
    )

    assert cold.suggestions == ()
    assert len(executor.handles) == 1

    resolved_loras = executor.handles[0].request.work(_Token())
    executor.handles[0].complete(result=resolved_loras)

    warm = provider.trigger_word_result(
        prefix="imp",
        prompt_text="mi",
        source_text="mi",
        source_identity=source_identity,
        query_identity=("tag", 0, 2, 2, 10),
        current_source_text=lambda: "mi",
        current_query_identity=lambda: ("tag", 0, 2, 2, 10),
        refresh_current_query=record_refresh,
    )

    assert [suggestion.tag for suggestion in warm.suggestions] == ["imp princess"]
    assert resolver.calls == ["mi"]
    assert refresh_calls == 1

    stale_key = provider.cache_key_for_prompt("stale prompt")
    provider.complete_for_tests(
        cache_key=stale_key,
        prompt_text="stale prompt",
        source_text="stale prompt",
        source_identity=PromptSourceIdentity(
            source_revision=8,
            source_length=len("stale prompt"),
        ),
        query_identity=("tag", 0, 12, 12, 10),
        scheduled_loras=(scheduled_lora,),
        current_source_text=lambda: "changed prompt",
        current_query_identity=lambda: ("tag", 0, 12, 12, 10),
        refresh_current_query=record_refresh,
    )

    assert refresh_calls == 1
    assert stale_key in provider.cached_cache_keys()

    failing_key = provider.cache_key_for_prompt("secret prompt")
    provider.fail_for_tests(
        cache_key=failing_key,
        prompt_text="secret prompt",
        error=RuntimeError("secret prompt leaked"),
    )

    assert failing_key not in provider.pending_cache_keys()
    assert failing_key not in provider.cached_cache_keys()
    assert "scheduled_lora_context.refresh.failed" in caplog.text
    assert "secret prompt leaked" not in caplog.text

    disabled_executor = _ScheduledLoraExecutor()
    disabled_provider = PromptScheduledLoraContextCoordinator(
        resolver=resolver,
        enabled=False,
        executor=cast(Any, disabled_executor),
    )

    disabled = disabled_provider.trigger_word_result(
        prefix="imp",
        prompt_text="mi",
        source_text="mi",
        source_identity=source_identity,
        query_identity=("tag", 0, 2, 2, 10),
        current_source_text=lambda: "mi",
        current_query_identity=lambda: ("tag", 0, 2, 2, 10),
        refresh_current_query=record_refresh,
    )

    assert disabled.suggestions == ()
    assert disabled_executor.handles == []
