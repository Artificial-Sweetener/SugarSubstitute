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

"""Exercise installer Close against blocked production preparation and native descendants."""

from collections.abc import Sequence
import json
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.release_sources import VersionBoundReleaseSource
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from sugarsubstitute_shared.installation_mutation import installation_mutation
from sugarsubstitute_shared.process_identity import (
    capture_process_identity,
    wait_for_process_exit,
)
from tests.launcher.installation_workflow.support import workflow_factory
from tests.launcher.support import launcher_test_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


@pytest.mark.platforms("windows")
@pytest.mark.parametrize("mode", ["worker", "descendant"])
def test_close_cancels_blocked_preparation_and_allows_reopening(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Close the real installer without releasing the read or manually killing a process."""
    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "installation")
    layout.root.mkdir()
    sentinel = layout.root / "active.txt"
    sentinel.write_bytes(b"preserve installation")
    source = VersionBoundReleaseSource("https://example.invalid/manifest.json", "1.2.3")

    def command(_layout: InstallLayout, arguments: Sequence[str]) -> tuple[str, ...]:
        """Insert controlled HTTPS I/O while retaining the actual child entrypoint."""
        assert len(arguments) == 1
        assert arguments[0].startswith("--repair-preparation-input=")
        return (
            sys.executable,
            "-m",
            "tests.launcher.repair.blocked_preparation_fixture",
            arguments[0],
            str(tmp_path),
            mode,
        )

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.repair_preparation_operation.build_launcher_ui_command",
        command,
    )
    handoffs: list[Path] = []
    failures: list[bool] = []
    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.repair_preparation_controller.launch_prepared_repair_helper",
        lambda *, request_path: handoffs.append(request_path),
    )
    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.installer_failure_presenter.InstallerFailurePresenter.show_failure",
        lambda *args, **kwargs: failures.append(True),
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=True,
        update_check_enabled=True,
        initial_release_source=source,
        workflow_factory=workflow_factory(),
    )
    try:
        window.show()
        window.view.repair_page.primary_button.click()
        identities: tuple[int, int | None] | None = None

        def blocked_process_identity_is_readable() -> bool:
            """Capture the cross-process marker only after Windows publishes it readably."""

            nonlocal identities
            try:
                payload = json.loads(
                    (tmp_path / "blocked.json").read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                return False
            if not isinstance(payload, dict):
                return False
            pid = payload.get("pid")
            child_pid = payload.get("child_pid")
            if type(pid) is not int or (
                child_pid is not None and type(child_pid) is not int
            ):
                return False
            identities = (pid, child_pid)
            return True

        wait_for_qt_condition(
            blocked_process_identity_is_readable,
            timeout_ms=15000,
        )
        assert identities is not None
        processes = [capture_process_identity(identities[0])]
        if identities[1] is not None:
            processes.append(capture_process_identity(identities[1]))
        window.close()
        wait_for_qt_condition(
            lambda: not window.isVisible() and not window.repair_preparation.running,
            timeout_ms=5000,
        )
        for process in processes:
            wait_for_process_exit(process, timeout_seconds=0)
        with installation_mutation(tmp_path / "descendant") as ownership:
            ownership.validate(tmp_path / "descendant")
        assert handoffs == []
        assert failures == []
        assert sentinel.read_bytes() == b"preserve installation"
        assert list((layout.root / ".repair").glob("preparation-*.json")) == []
        window.show()
        assert window.isVisible()
        window.close()
        assert not window.isVisible()
    finally:
        window.close()
        wait_for_qt_condition(
            lambda: not window.repair_preparation.running, timeout_ms=15000
        )
        window.close()
        window.deleteLater()
        application.processEvents()
