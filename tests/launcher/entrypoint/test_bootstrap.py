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

"""Test packaged launcher-bootstrap failure observability."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher import __main__ as launcher_bootstrap
from sugarsubstitute_shared.crash_reporting.protocol import CleanExitOutcome


class _RecordingCrashRuntime:
    """Record whether a supervised launcher child authenticates completion."""

    def __init__(self) -> None:
        """Create a runtime with no terminal outcome."""

        self.clean_exit_outcome: CleanExitOutcome | None = None

    def request_clean_exit(self, outcome: CleanExitOutcome) -> None:
        """Record the one controlled terminal outcome."""

        self.clean_exit_outcome = outcome


def test_launcher_bootstrap_returns_success_without_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A successful launcher should preserve its normal exit code and no log."""

    launcher_dir = tmp_path / "launcher"
    launcher_dir.mkdir()
    (launcher_dir / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert launcher_bootstrap.run_launcher(lambda: 0) == 0
    assert not (launcher_dir / "logs" / "launcher-bootstrap.log").exists()


def test_supervised_launcher_child_authenticates_only_normal_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The parent may trust a launcher UI exit only after bootstrap returns."""

    runtime = _RecordingCrashRuntime()
    monkeypatch.setattr(
        launcher_bootstrap,
        "_install_supervised_crash_runtime",
        lambda: runtime,
    )

    assert launcher_bootstrap.run_launcher(lambda: 7) == 7
    assert runtime.clean_exit_outcome is CleanExitOutcome.CLOSED


def test_launcher_bootstrap_records_installed_pre_main_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An installed windowed bundle crash should retain its complete traceback."""

    install_root = tmp_path / "SugarSubstitute"
    launcher_dir = install_root / "launcher"
    launcher_dir.mkdir(parents=True)
    (launcher_dir / "config.json").write_text("{}", encoding="utf-8")
    invocation_path = install_root / "SugarSubstitute"
    monkeypatch.setattr(sys, "argv", [str(invocation_path)])
    monkeypatch.chdir(tmp_path)

    def fail_before_main() -> int:
        """Represent an unexpected packaged import or startup failure."""

        raise RuntimeError("packaged bootstrap exploded")

    runtime = _RecordingCrashRuntime()
    monkeypatch.setattr(
        launcher_bootstrap,
        "_install_supervised_crash_runtime",
        lambda: runtime,
    )

    with pytest.raises(RuntimeError, match="packaged bootstrap exploded"):
        launcher_bootstrap.run_launcher(fail_before_main)

    failure_log = launcher_dir / "logs" / "launcher-bootstrap.log"
    assert failure_log.is_file()
    failure = failure_log.read_text(encoding="utf-8")
    assert "RuntimeError: packaged bootstrap exploded" in failure
    assert "fail_before_main" in failure
    assert "RuntimeError: packaged bootstrap exploded" in capsys.readouterr().err
    assert runtime.clean_exit_outcome is None
