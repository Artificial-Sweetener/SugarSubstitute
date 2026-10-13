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

"""Validate the owned helper handoff without creating a desktop process."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.baseline_recovery_bootstrap import (
    run_baseline_recovery_bootstrap,
)
from launcher.sugarsubstitute_launcher.baseline_recovery_request import (
    BaselineRecoveryRequest,
)
from sugarsubstitute_shared.process_identity import ProcessIdentity


def test_recovery_request_roundtrip_and_namespace(tmp_path: Path) -> None:
    """Preserve invocation intent and process incarnations only in the owned namespace."""
    root = tmp_path / "installation"
    path = root / "launcher" / "updates" / "recovery" / "owned" / "request.json"
    request = BaselineRecoveryRequest(
        root.resolve(),
        ("--install-root", str(root), "unicode-\u03a9"),
        (ProcessIdentity(pid=123, created_at=456.75),),
        False,
    )
    request.save(path)
    assert BaselineRecoveryRequest.load(path) == request
    with pytest.raises(ValueError, match="escapes"):
        request.save(tmp_path / "unowned.json")
    unowned = tmp_path / "unowned.json"
    unowned.write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="escapes"):
        BaselineRecoveryRequest.load(unowned)


@pytest.mark.parametrize("created_at", [0, -1, float("inf"), float("nan"), True, "1"])
def test_recovery_request_rejects_invalid_process_incarnation(
    tmp_path: Path,
    created_at: object,
) -> None:
    """Never turn an invalid persisted process incarnation into a wait on a reused PID."""
    root = tmp_path / "installation"
    path = root / "launcher" / "updates" / "recovery" / "owned" / "request.json"
    request = BaselineRecoveryRequest(root, (), (), False)
    request.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["wait_identities"] = [{"pid": 123, "created_at": created_at}]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        BaselineRecoveryRequest.load(path)


def test_source_invocation_does_not_enter_frozen_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Source tools cannot accidentally schedule a copied native launcher."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert (
        run_baseline_recovery_bootstrap(("--recover-launcher-baseline", "missing"))
        is None
    )


@pytest.mark.platforms("windows")
def test_unowned_frozen_helper_is_rejected_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrelated executable cannot act as the copied helper for a valid request."""
    root = tmp_path / "installation"
    path = root / "launcher" / "updates" / "recovery" / "owned" / "request.json"
    BaselineRecoveryRequest(root, (), (), False).save(path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Unowned.exe"))
    with pytest.raises(ValueError, match="outside its request owner"):
        run_baseline_recovery_bootstrap(("--recover-launcher-baseline", str(path)))
    assert path.is_file()
    assert not (root / "launcher" / "updates" / "transaction.json").exists()
