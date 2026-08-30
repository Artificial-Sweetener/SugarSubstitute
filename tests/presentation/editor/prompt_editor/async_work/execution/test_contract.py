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

"""Verify immutable prompt-editor asynchronous execution contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass
from typing import Any, cast

import pytest

from substitute.presentation.editor.prompt_editor.async_work.cancellation import (
    PromptEditorCancellationSource,
)
from substitute.presentation.editor.prompt_editor.async_work.execution import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    prompt_async_identity_from_task,
    prompt_task_identity_from_async,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)


@pytest.mark.parametrize(
    "type_object",
    [
        PromptAsyncRequest,
        PromptAsyncRequestContext,
        PromptAsyncResultIdentity,
        PromptAsyncTaskOutcome,
    ],
)
def test_async_execution_value_types_are_frozen_slotted(type_object: object) -> None:
    """Keep execution value types immutable and memory-stable."""

    assert is_dataclass(type_object)
    assert getattr(type_object, "__slots__", None) is not None

    identity = PromptAsyncResultIdentity(request_id=1)
    with pytest.raises(FrozenInstanceError):
        cast(Any, identity).request_id = 2


@pytest.mark.parametrize(
    ("field_name", "identity_kwargs"),
    [
        ("request_id", {"request_id": -1}),
        ("cancellation_generation", {"request_id": 1, "cancellation_generation": -1}),
    ],
)
def test_async_result_identity_rejects_negative_integer_fields(
    field_name: str,
    identity_kwargs: dict[str, int],
) -> None:
    """Reject invalid revision-like identity values."""

    with pytest.raises(ValueError, match=field_name):
        cast(Any, PromptAsyncResultIdentity)(**identity_kwargs)


@pytest.mark.parametrize(
    ("context_kwargs", "field_name"),
    [
        ({"operation": "", "reason": "text_changed"}, "operation"),
        ({"operation": "semantic_refresh", "reason": "   "}, "reason"),
        (
            {
                "operation": "semantic_refresh",
                "reason": "text_changed",
                "safe_fields": ((" ", 1),),
            },
            "safe_fields field name",
        ),
    ],
)
def test_async_request_context_rejects_blank_prompt_safe_labels(
    context_kwargs: dict[str, object], field_name: str
) -> None:
    """Require meaningful prompt-safe context labels."""

    with pytest.raises(ValueError, match=field_name):
        cast(Any, PromptAsyncRequestContext)(**context_kwargs)


def test_async_request_does_not_execute_work_during_construction() -> None:
    """Store task callables without running them."""

    executed = False

    def work(_token: object) -> int:
        """Record invocation and return a stable work result."""

        nonlocal executed
        executed = True
        return 7

    request = PromptAsyncRequest(
        identity=PromptAsyncResultIdentity(
            request_id=4,
            editor_session_id="session",
            source_identity=PromptSourceIdentity(source_revision=12, source_length=32),
            feature_profile_id="features",
            scene_context_id="scene",
            cube_context_id="cube",
            query_identity=("tag", "cat"),
            cancellation_generation=3,
        ),
        context=PromptAsyncRequestContext(
            operation="semantic_refresh",
            reason="text_changed",
            safe_fields=(("source_length", 32),),
        ),
        work=work,
    )

    assert executed is False
    assert request.identity.source_identity == PromptSourceIdentity(
        source_revision=12, source_length=32
    )
    assert request.context.safe_fields == (("source_length", 32),)
    assert request.work(PromptEditorCancellationSource(generation=1)) == 7
    assert executed is True


def test_async_source_identity_round_trips_through_shared_execution_parts() -> None:
    """Preserve typed source lineage across the generic executor boundary."""

    identity = PromptAsyncResultIdentity(
        request_id=9,
        editor_session_id="session",
        source_identity=PromptSourceIdentity(source_revision=21, source_length=144),
        cancellation_generation=5,
    )

    task_identity = prompt_task_identity_from_async(identity)

    assert task_identity.field_value("source_revision") == 21
    assert task_identity.field_value("source_length") == 144
    assert prompt_async_identity_from_task(task_identity) == identity


def test_async_task_outcome_rejects_ambiguous_states() -> None:
    """Reject conflicting task completion states."""

    identity = PromptAsyncResultIdentity(request_id=1)
    context = PromptAsyncRequestContext(operation="test", reason="unit")

    with pytest.raises(ValueError, match="cancelled"):
        PromptAsyncTaskOutcome(
            identity=identity,
            context=context,
            error=RuntimeError("failed"),
            cancelled=True,
        )
    with pytest.raises(ValueError, match="cancelled"):
        PromptAsyncTaskOutcome(
            identity=identity, context=context, result=1, cancelled=True
        )
    with pytest.raises(ValueError, match="failed"):
        PromptAsyncTaskOutcome(
            identity=identity,
            context=context,
            result=1,
            error=RuntimeError("failed"),
        )
