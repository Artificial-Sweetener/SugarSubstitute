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

"""Test shared compatibility behavior for readiness receipts."""

from __future__ import annotations

import pytest

from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
    READINESS_SCHEMA_VERSION,
    REQUIRED_READINESS_MILESTONES,
    without_application_readiness_environment,
)


def test_legacy_readiness_receipt_remains_parseable_but_not_main_shell() -> None:
    """Parse schema-one evidence without claiming main-shell readiness."""

    receipt = ApplicationReadinessReceipt.from_json(
        {"pid": 123, "schema_version": 1, "token": "legacy-token"}
    )

    assert READINESS_SCHEMA_VERSION > 1
    assert receipt.surface is ApplicationReadinessSurface.LEGACY_VISIBLE_SHELL
    assert receipt.parent_pid is None


def test_schema_two_readiness_receipt_remains_parseable_without_parent() -> None:
    """Retain prior main-shell evidence while withholding descendant identity."""

    receipt = ApplicationReadinessReceipt.from_json(
        {
            "pid": 123,
            "schema_version": 2,
            "surface": "main_shell",
            "token": "legacy-token",
        }
    )

    assert receipt.surface is ApplicationReadinessSurface.MAIN_SHELL
    assert receipt.parent_pid is None


def test_current_readiness_receipt_requires_a_positive_parent_pid() -> None:
    """Reject current process-chain evidence without a valid direct parent."""

    try:
        ApplicationReadinessReceipt.from_json(
            {
                "parent_pid": None,
                "pid": 123,
                "schema_version": READINESS_SCHEMA_VERSION,
                "surface": "main_shell",
                "token": "launch-token",
            }
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Current readiness evidence accepted no parent PID.")


def test_schema_four_receipt_remains_parseable_without_attestation_chain() -> None:
    """Read the previous milestone contract without inventing process hops."""

    receipt = ApplicationReadinessReceipt.from_json(
        {
            "milestones": list(REQUIRED_READINESS_MILESTONES),
            "parent_pid": 122,
            "pid": 123,
            "schema_version": 4,
            "surface": "main_shell",
            "token": "legacy-token",
        }
    )

    assert receipt.attester_pids == ()


def test_current_receipt_rejects_invalid_attestation_chain() -> None:
    """Reject non-positive or non-integer process identities in the chain."""

    payload = ApplicationReadinessReceipt(
        pid=123,
        parent_pid=122,
        token="launch-token",
        surface=ApplicationReadinessSurface.MAIN_SHELL,
    ).to_json()
    payload["attester_pids"] = [121, 0]

    try:
        ApplicationReadinessReceipt.from_json(payload)
    except ValueError:
        pass
    else:
        raise AssertionError("Current readiness evidence accepted an invalid chain.")


@pytest.mark.parametrize("schema_version", range(1, READINESS_SCHEMA_VERSION + 1))
def test_receipt_serializes_for_every_supported_supervisor_schema(
    schema_version: int,
) -> None:
    """A current launcher must relay readiness to every historical supervisor."""

    source = ApplicationReadinessReceipt(
        pid=123,
        parent_pid=122,
        token="launch-token",
        surface=ApplicationReadinessSurface.MAIN_SHELL,
        attester_pids=(121,),
    )

    payload = source.to_json(schema_version=schema_version)
    parsed = ApplicationReadinessReceipt.from_json(payload)

    assert payload["schema_version"] == schema_version
    assert parsed.pid == source.pid
    assert parsed.token == source.token
    assert ("parent_pid" in payload) is (schema_version >= 3)
    assert ("milestones" in payload) is (schema_version >= 4)
    assert ("attester_pids" in payload) is (schema_version >= 5)
    if schema_version == 1:
        assert parsed.surface is ApplicationReadinessSurface.LEGACY_VISIBLE_SHELL
    else:
        assert parsed.surface is source.surface


def test_detached_environment_removes_every_readiness_contract() -> None:
    """A top-level relaunch must not retain direct or delegated readiness state."""

    source = {
        "SUGAR_SUBSTITUTE_READINESS_PATH": "direct.json",
        "SUGAR_SUBSTITUTE_READINESS_TOKEN": "direct-token",
        "SUGAR_SUBSTITUTE_READINESS_SCHEMA": "5",
        "SUGAR_SUBSTITUTE_READINESS_DELEGATION_PATH": "outer.json",
        "SUGAR_SUBSTITUTE_READINESS_DELEGATION_TOKEN": "outer-token",
        "SUGAR_SUBSTITUTE_READINESS_DELEGATION_SCHEMA": "3",
        "PRESERVED": "yes",
    }

    detached = without_application_readiness_environment(source)

    assert detached == {"PRESERVED": "yes"}
