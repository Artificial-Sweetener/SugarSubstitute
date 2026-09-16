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

"""Verify selected-folder admission through the production installer surface."""

from pathlib import Path

import pytest
from PySide6.QtTest import QSignalSpy

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.localization import (
    build_launcher_localization_runtime,
)
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)
from tests.launcher.installation_workflow.support import (
    advance_to_install_location,
    close_and_delete_launcher_window,
    release_source_for_test,
    wait_for_launcher_condition,
    workflow_factory,
)
from tests.launcher.support import launcher_test_application


@pytest.mark.parametrize("frozen_setup", [False, True])
def test_existing_app_retires_installer_without_writes_or_active_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, frozen_setup: bool
) -> None:
    """Present the existing owner and finish Qt workers before process exit."""
    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "selected")
    invocation = ApplicationInvocation.capture(["setup"])
    existing = ApplicationInstanceBroker.elect(
        install_root=layout.root, invocation=invocation
    )
    bootstrap = ApplicationInstanceBroker.elect(
        install_root=tmp_path / "bootstrap", invocation=invocation
    )
    assert existing is not None and bootstrap is not None
    received: list[ApplicationInvocation] = []

    def present_existing(request: ApplicationInvocation) -> str:
        """Acknowledge presentation from the real native broker request."""
        received.append(request)
        return "main-shell"

    existing.bind_startup_presenter(present_existing)
    client = ApplicationSupervisorClient.connect_from_environment(
        bootstrap.child_environment({})
    )
    assert client is not None
    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.main_window.current_frozen_executable_path",
        lambda: tmp_path / "setup.exe" if frozen_setup else None,
    )
    localization = build_launcher_localization_runtime(
        application, layout=layout, locale_override="en"
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=False,
        initial_release_source=release_source_for_test(),
        localization_manager=localization.manager,
        workflow_factory=workflow_factory(
            admit_installation=lambda target: client.claim_installation(target.root)
        ),
    )
    worker_states: list[tuple[bool, bool]] = []
    completed = QSignalSpy(window.handoff_completed)
    failures = QSignalSpy(window.execution.initial_failed)
    setup_started = QSignalSpy(window.execution.setup_succeeded)
    window.handoff_completed.connect(
        lambda: worker_states.append(
            (window.execution.initial_running, window.execution.setup_running)
        )
    )
    try:
        window.show()
        advance_to_install_location(window)
        window.view.primary_button.click()
        wait_for_launcher_condition(application, lambda: completed.count() == 1)
        assert worker_states == [(False, False)]
        assert not window.isVisible()
        assert failures.count() == 0
        assert setup_started.count() == 0
        assert len(received) == 1
        assert not layout.root.exists()
    finally:
        close_and_delete_launcher_window(window)
        localization.manager.close()
        client.close()
        bootstrap.close()
        existing.close()
