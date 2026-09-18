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

"""Preserve recovery guidance through bounded cross-generation UI requests."""

import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
    InstanceRecoveryRequest,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceFailureReason,
)


@pytest.mark.parametrize("reason", list(ApplicationInstanceFailureReason))
def test_recovery_request_round_trip_preserves_reason(
    tmp_path: Path, reason: ApplicationInstanceFailureReason
) -> None:
    """Retain the diagnosis with the authenticated owner-action request."""
    request, path = InstanceRecoveryRequest.create(tmp_path, reason=reason)
    request.write(path)
    assert InstanceRecoveryRequest.read(path) == request


def test_legacy_request_without_reason_keeps_generic_recovery(tmp_path: Path) -> None:
    """Read the version-one host request emitted by earlier launcher generations."""
    request, path = InstanceRecoveryRequest.create(
        tmp_path,
        reason=ApplicationInstanceFailureReason.UNAVAILABLE,
    )
    request.write(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["reason"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert InstanceRecoveryRequest.read(path) == request


@pytest.mark.parametrize("invalid", [None, True, 10, "unknown-reason"])
def test_invalid_recovery_reason_is_rejected(tmp_path: Path, invalid: object) -> None:
    """Reject malformed guidance rather than presenting an invented diagnosis."""
    request, path = InstanceRecoveryRequest.create(
        tmp_path,
        reason=ApplicationInstanceFailureReason.UNAVAILABLE,
    )
    request.write(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["reason"] = invalid
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        InstanceRecoveryRequest.read(path)


def test_oversized_recovery_exchange_is_rejected_before_json_parsing(
    tmp_path: Path,
) -> None:
    """A damaged private exchange cannot force an unbounded launcher read."""
    _request, path = InstanceRecoveryRequest.create(
        tmp_path,
        reason=ApplicationInstanceFailureReason.UNAVAILABLE,
    )
    path.write_bytes(b"{" + b" " * (17 * 1024) + b"}")
    with pytest.raises(ValueError, match="size limit"):
        InstanceRecoveryRequest.read(path)
