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

"""Tests for prompt-editor async stale-result freshness validation."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncResultIdentity,
    PromptStaleResultGuard,
)


def test_stale_result_guard_accepts_matching_required_identity_fields() -> None:
    """Freshness validation should accept matching required identity fields."""

    guard = PromptStaleResultGuard()
    result_identity = PromptAsyncResultIdentity(
        request_id=4,
        editor_session_id="session-a",
        source_revision=12,
        cancellation_generation=2,
    )
    current_identity = PromptAsyncResultIdentity(
        request_id=5,
        editor_session_id="session-a",
        source_revision=12,
        cancellation_generation=2,
    )

    decision = guard.validate(
        result_identity=result_identity,
        current_identity=current_identity,
        required_fields=(
            "editor_session_id",
            "source_revision",
            "cancellation_generation",
        ),
    )

    assert decision.is_fresh is True
    assert decision.drop_reason == "fresh"
    assert decision.mismatches == ()


def test_stale_result_guard_rejects_identity_mismatch() -> None:
    """Freshness validation should report prompt-safe mismatched fields."""

    guard = PromptStaleResultGuard()

    decision = guard.validate(
        result_identity=PromptAsyncResultIdentity(
            request_id=4,
            editor_session_id="session-a",
            source_revision=11,
        ),
        current_identity=PromptAsyncResultIdentity(
            request_id=5,
            editor_session_id="session-a",
            source_revision=12,
        ),
        required_fields=("editor_session_id", "source_revision"),
    )

    assert decision.is_fresh is False
    assert decision.drop_reason == "identity_mismatch"
    assert [
        (mismatch.field_name, mismatch.expected, mismatch.actual)
        for mismatch in decision.mismatches
    ] == [("source_revision", 12, 11)]


def test_stale_result_guard_fails_closed_when_required_identity_is_missing() -> None:
    """Freshness validation should reject missing required identity components."""

    guard = PromptStaleResultGuard()

    decision = guard.validate(
        result_identity=PromptAsyncResultIdentity(
            request_id=4,
            editor_session_id="session-a",
        ),
        current_identity=PromptAsyncResultIdentity(
            request_id=5,
            editor_session_id="session-a",
            source_revision=12,
        ),
        required_fields=("editor_session_id", "source_revision"),
    )

    assert decision.is_fresh is False
    assert decision.drop_reason == "missing_identity"
    assert [
        (mismatch.field_name, mismatch.expected, mismatch.actual)
        for mismatch in decision.mismatches
    ] == [("source_revision", 12, None)]


def test_stale_result_guard_ignores_optional_unrequested_identity_fields() -> None:
    """Freshness validation should ignore fields omitted from required_fields."""

    guard = PromptStaleResultGuard()

    decision = guard.validate(
        result_identity=PromptAsyncResultIdentity(
            request_id=4,
            editor_session_id="session-a",
            query_identity=("tag", 1),
        ),
        current_identity=PromptAsyncResultIdentity(
            request_id=5,
            editor_session_id="session-a",
            query_identity=("tag", 2),
        ),
        required_fields=("editor_session_id",),
    )

    assert decision.is_fresh is True


def test_stale_result_guard_rejects_empty_required_fields() -> None:
    """Freshness validation should require an explicit publication identity."""

    guard = PromptStaleResultGuard()

    with pytest.raises(ValueError, match="required_fields"):
        guard.validate(
            result_identity=PromptAsyncResultIdentity(request_id=1),
            current_identity=PromptAsyncResultIdentity(request_id=2),
            required_fields=(),
        )
