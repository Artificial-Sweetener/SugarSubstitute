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

"""Verify authenticated crash lifecycle and privacy contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sugarsubstitute_shared.crash_reporting.protocol import (
    CRASH_RUN_TOKEN_ENV,
    CleanExitOutcome,
    CrashRunContext,
)
from sugarsubstitute_shared.crash_reporting.redaction import CrashReportRedactor


def test_run_context_round_trips_through_child_environment(tmp_path: Path) -> None:
    """The application should receive every supervisor-owned crash path together."""

    context = CrashRunContext.create(tmp_path / "diagnostics")

    inherited = CrashRunContext.from_environment(context.environment({"KEEP": "yes"}))

    assert inherited == context


def test_partial_crash_environment_fails_closed() -> None:
    """A launch must not silently run under incomplete crash supervision."""

    with pytest.raises(ValueError, match="incomplete"):
        CrashRunContext.from_environment({CRASH_RUN_TOKEN_ENV: "orphaned"})


def test_clean_exit_requires_matching_signed_intent_and_receipt(tmp_path: Path) -> None:
    """Exit code alone must never prove that an application terminated cleanly."""

    context = CrashRunContext.create(tmp_path / "diagnostics")

    assert context.validates_clean_exit(process_id=42) is False
    context.write_exit_intent(CleanExitOutcome.CLOSED, process_id=42)
    assert context.validates_clean_exit(process_id=42) is False
    context.write_exit_receipt(CleanExitOutcome.CLOSED, process_id=42)
    assert context.validates_clean_exit(process_id=42) is True


def test_tampered_exit_receipt_is_rejected(tmp_path: Path) -> None:
    """Another local process cannot forge a clean exit without the run token."""

    context = CrashRunContext.create(tmp_path / "diagnostics")
    context.write_exit_intent(CleanExitOutcome.CLOSED, process_id=42)
    context.write_exit_receipt(CleanExitOutcome.CLOSED, process_id=42)
    payload = json.loads(context.exit_receipt_path.read_text(encoding="utf-8"))
    payload["outcome"] = CleanExitOutcome.RESTART.value
    context.exit_receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    assert context.validates_clean_exit(process_id=42) is False


def test_crash_redactor_removes_paths_and_secret_values(tmp_path: Path) -> None:
    """Copyable reports should retain context without exposing common credentials."""

    home = tmp_path / "Users" / "Ada"
    install = tmp_path / "SugarSubstitute"
    redactor = CrashReportRedactor(home=home, install_root=install)
    source = (
        f"File {home / 'project' / 'main.py'}\n"
        f"install={str(install).replace('\\', '/')}\n"
        "api_key=abc123 password: hunter2 Authorization=Bearer-token"
    )

    rendered = redactor.text(source)

    assert str(home) not in rendered
    assert str(install) not in rendered
    assert "abc123" not in rendered
    assert "hunter2" not in rendered
    assert "Bearer-token" not in rendered
    assert "<user-home>" in rendered
    assert "<install-root>" in rendered


def test_crash_redactor_sanitizes_split_and_inline_arguments(tmp_path: Path) -> None:
    """Sensitive command-line values should never enter durable incidents."""

    redactor = CrashReportRedactor(home=tmp_path, install_root=None)

    assert redactor.arguments(
        ("main.py", "--api-key=secret-one", "--password", "secret-two", "--safe=yes")
    ) == ("main.py", "--api-key=<redacted>", "--password", "<redacted>", "--safe=yes")
