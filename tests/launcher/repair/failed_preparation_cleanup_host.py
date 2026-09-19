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

"""Exercise installer retirement when the preparation child's native kill fails."""

from collections.abc import Mapping, Sequence
from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import pytest

from launcher.sugarsubstitute_launcher import repair_process_supervisor as supervision
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_execution import (
    ChildProcess,
    spawn_supervised_process,
)
from launcher.sugarsubstitute_launcher.release_sources import VersionBoundReleaseSource
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from sugarsubstitute_shared.installation_mutation import (
    InstallationMutationBusyError,
    installation_mutation,
)
from tests.launcher.installation_workflow.support import workflow_factory
from tests.launcher.repair.failed_cleanup_host import FailedTermination


def main() -> int:
    """Close the real installer while its blocked preparation owns a native descendant."""
    root = Path(sys.argv[1])
    application = QApplication(sys.argv[:1])
    retained: list[FailedTermination] = []

    def start(
        command: Sequence[str],
        *,
        environment: Mapping[str, str],
        startup_log_path: Path,
    ) -> tuple[ChildProcess, Path]:
        """Keep native containment intact while failing only the explicit termination call."""
        process, log = spawn_supervised_process(
            command, environment=environment, startup_log_path=startup_log_path
        )
        boundary = FailedTermination(process)
        retained.append(boundary)
        return boundary, log

    def command(_layout: InstallLayout, arguments: Sequence[str]) -> tuple[str, ...]:
        """Run real preparation with the controlled blocked network read fixture."""
        return (
            sys.executable,
            "-m",
            "tests.launcher.repair.blocked_preparation_fixture",
            arguments[0],
            str(root),
            "descendant",
        )

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(supervision, "spawn_supervised_process", start)
        patch.setattr(
            "launcher.sugarsubstitute_launcher.repair_preparation_operation.build_launcher_ui_command",
            command,
        )
        window = LauncherMainWindow(
            initial_layout=InstallLayout.from_root(root / "installation"),
            continue_install=False,
            repair=True,
            update_check_enabled=True,
            initial_release_source=VersionBoundReleaseSource(
                "https://example.invalid/manifest.json", "1.2.3"
            ),
            workflow_factory=workflow_factory(),
        )
        observer = QTimer(window)

        def close_when_blocked() -> None:
            """Use ordinary Close only after descendant ownership is demonstrated."""
            if not (root / "blocked.json").exists():
                return
            observer.stop()
            with pytest.raises(InstallationMutationBusyError):
                with installation_mutation(root / "descendant"):
                    pytest.fail("Fixture descendant did not hold ownership")
            (root / "cancellation-observed.txt").write_text(
                "descendant-owned", encoding="utf-8"
            )
            window.close()

        observer.timeout.connect(close_when_blocked)
        observer.start(10)
        QTimer.singleShot(15000, lambda: application.exit(91))
        QTimer.singleShot(0, window.view.repair_page.primary_button.click)
        window.show()
        return int(application.exec())


if __name__ == "__main__":
    raise SystemExit(main())
