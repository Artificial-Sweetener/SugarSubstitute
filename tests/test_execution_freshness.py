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

"""Test reusable stale-result validation."""

from __future__ import annotations

import pytest

from substitute.application.execution import (
    FreshnessRequirement,
    StaleResultGuard,
    TaskIdentity,
)


def _identity(*, request_id: int = 1, workflow_id: str | None = "wf-1") -> TaskIdentity:
    """Build one test identity."""

    return TaskIdentity(
        request_id=request_id,
        domain="workflow",
        parts=(("workflow_id", workflow_id),),
    )


def test_stale_result_guard_accepts_matching_identity() -> None:
    """Accept results that match all required identity fields."""

    decision = StaleResultGuard().validate(
        result_identity=_identity(),
        current_identity=_identity(),
        required_fields=("request_id", "workflow_id"),
    )

    assert decision.is_fresh is True
    assert decision.drop_reason == "fresh"
    assert decision.mismatches == ()


def test_stale_result_guard_reports_identity_mismatch() -> None:
    """Report mismatched fields without raising."""

    decision = StaleResultGuard().validate(
        result_identity=_identity(request_id=1),
        current_identity=_identity(request_id=2),
        required_fields=FreshnessRequirement(("request_id",)),
    )

    assert decision.is_fresh is False
    assert decision.drop_reason == "identity_mismatch"
    assert decision.mismatches[0].field_name == "request_id"


def test_stale_result_guard_reports_missing_identity() -> None:
    """Treat missing required values as stale."""

    decision = StaleResultGuard().validate(
        result_identity=_identity(workflow_id=None),
        current_identity=_identity(workflow_id="wf-1"),
        required_fields=("workflow_id",),
    )

    assert decision.is_fresh is False
    assert decision.drop_reason == "missing_identity"


def test_freshness_requirement_rejects_empty_fields() -> None:
    """Require callers to state the fields that matter."""

    with pytest.raises(ValueError, match="required_fields"):
        FreshnessRequirement(())


def test_explicit_drop_decisions_are_available() -> None:
    """Expose standard non-identity drop reasons."""

    guard = StaleResultGuard()

    assert guard.cancelled().drop_reason == "cancelled"
    assert guard.scope_closed().drop_reason == "scope_closed"
    assert guard.receiver_destroyed().drop_reason == "receiver_destroyed"
