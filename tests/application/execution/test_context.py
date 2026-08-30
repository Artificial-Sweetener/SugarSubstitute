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

"""Test execution context and identity value validation."""

from __future__ import annotations

import pytest

from substitute.application.execution import ExecutionContext, TaskIdentity


def test_execution_context_requires_labels() -> None:
    """Reject blank labels before diagnostic context reaches workers."""

    with pytest.raises(ValueError, match="operation"):
        ExecutionContext(operation="", reason="refresh", lane="settings_io")
    with pytest.raises(ValueError, match="reason"):
        ExecutionContext(operation="load", reason=" ", lane="settings_io")
    with pytest.raises(ValueError, match="lane"):
        ExecutionContext(operation="load", reason="refresh", lane="")


def test_execution_context_accepts_allowlisted_safe_fields() -> None:
    """Retain approved safe diagnostic fields."""

    context = ExecutionContext(
        operation="load",
        reason="refresh",
        lane="settings_io",
        scope_id="settings",
        owner_id="generation-page",
        safe_fields=(("workflow_id", "wf-1"), ("request_id", 3)),
    )

    assert context.field_value("workflow_id") == "wf-1"
    assert context.field_value("request_id") == 3


@pytest.mark.parametrize(
    "value",
    [
        "Artificial-Sweetener/Base-Cubes/Anima/Promptmask Detailer.cube",
        "Tokenizer",
        "Secret Garden",
    ],
)
def test_execution_context_does_not_infer_sensitivity_from_value_text(
    value: str,
) -> None:
    """Accept ordinary identifier text without guessing whether it is sensitive."""

    context = ExecutionContext(
        operation="load",
        reason="cube_load",
        lane="cube_load",
        safe_fields=(("cube_id", value),),
    )

    assert context.field_value("cube_id") == value


def test_execution_context_rejects_unapproved_safe_field_names() -> None:
    """Keep diagnostics constrained to the central safe-field allowlist."""

    with pytest.raises(ValueError, match="not an approved"):
        ExecutionContext(
            operation="load",
            reason="refresh",
            lane="settings_io",
            safe_fields=(("unreviewed_field", "value"),),
        )


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("status", "C:\\Users\\person\\secret.txt"),
        ("status", "/home/person/secret.txt"),
        ("status", 'Traceback (most recent call last):\n  File "x.py"'),
        ("api_key", "redacted"),
    ],
)
def test_execution_context_rejects_sensitive_safe_fields(
    field_name: str,
    value: str,
) -> None:
    """Prevent unapproved fields, local paths, and traces from safe fields."""

    with pytest.raises(ValueError):
        ExecutionContext(
            operation="load",
            reason="refresh",
            lane="settings_io",
            safe_fields=((field_name, value),),
        )


def test_task_identity_validates_and_exposes_fields() -> None:
    """Expose base and custom identity fields for stale-result guards."""

    identity = TaskIdentity(
        request_id=7,
        domain="prompt",
        parts=(("workflow_id", "wf-1"),),
        cancellation_generation=2,
    )

    assert identity.field_value("request_id") == 7
    assert identity.field_value("domain") == "prompt"
    assert identity.field_value("workflow_id") == "wf-1"
    assert identity.field_value("cancellation_generation") == 2


def test_task_identity_rejects_ambiguous_values() -> None:
    """Reject negative counters, blank labels, and duplicate fields."""

    with pytest.raises(ValueError, match="request_id"):
        TaskIdentity(request_id=-1, domain="prompt")
    with pytest.raises(ValueError, match="domain"):
        TaskIdentity(request_id=1, domain="")
    with pytest.raises(ValueError, match="more than once"):
        TaskIdentity(
            request_id=1,
            domain="prompt",
            parts=(("workflow_id", "a"), ("workflow_id", "b")),
        )
