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

"""Prove startup admission against a real concurrent installation writer."""

from concurrent.futures import ThreadPoolExecutor
import logging
from pathlib import Path
from threading import Event

import pytest

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.startup_plan import LauncherStartupCandidate
from launcher.sugarsubstitute_launcher.startup_recovery import recover_startup_candidate
from sugarsubstitute_shared.installation_mutation import installation_mutation
from launcher.sugarsubstitute_launcher.application_startup_contract import (
    InstallationStartupDeferred,
    ApplicationStartupCancelled,
)
from launcher.sugarsubstitute_launcher.startup_installation_wait import (
    StartupInstallationWait,
)


def test_startup_waits_for_writer_before_assessing_a_journal_free_installation(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Reproduce the update gap without treating native contention as corruption."""
    layout = InstallLayout.from_root(tmp_path / "install")
    owned = Event()
    release = Event()

    class ContentionBarrier(logging.Handler):
        """Release the writer only after startup actually encounters its native claim."""

        def emit(self, record: logging.LogRecord) -> None:
            """Make contention, rather than elapsed time, authorize writer completion."""
            if record.name == "sugarsubstitute_shared.installation_mutation":
                if (
                    record.getMessage()
                    == "Installation mutation is owned by another execution"
                ):
                    release.set()

    def write_installation() -> None:
        """Hold real kernel ownership until the competing startup proves contention."""
        with installation_mutation(layout.root):
            owned.set()
            assert release.wait(10), "Startup never observed the installation owner"
            LauncherConfig.from_layout(layout=layout).save(layout.config_path)

    barrier = ContentionBarrier()
    caplog.set_level(logging.INFO)
    logging.getLogger().addHandler(barrier)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            writer = executor.submit(write_installation)
            try:
                assert owned.wait(10), "Native writer did not acquire ownership"
                candidate = recover_startup_candidate(
                    LauncherStartupCandidate(layout, False)
                )
                assert release.is_set(), (
                    "Startup assessed the installation during mutation"
                )
                assert candidate.installed_config_found
                assert (
                    LauncherConfig.load(layout.config_path).install_root == layout.root
                )
            finally:
                release.set()
                writer.result(timeout=10)
    finally:
        logging.getLogger().removeHandler(barrier)


@pytest.mark.parametrize("cancel", [False, True])
def test_wait_timeout_or_cancellation_preserves_the_current_writer(
    tmp_path: Path, cancel: bool
) -> None:
    """Never steal ownership or change prepared files when startup cannot continue."""
    root = tmp_path / "install"
    now = [0.0]
    waited = Event()
    prepared = root / "prepared.bin"

    def wait(seconds: float) -> None:
        """Advance the controlled deadline while leaving native ownership intact."""
        now[0] += seconds
        waited.set()

    admission = StartupInstallationWait(
        timeout_seconds=0.1,
        monotonic=lambda: now[0],
        wait=wait,
        cancellation_requested=lambda: cancel and waited.is_set(),
    )
    with installation_mutation(root):
        prepared.write_bytes(b"prepared update")
        with pytest.raises(
            ApplicationStartupCancelled if cancel else InstallationStartupDeferred
        ):
            with admission.acquire(root):
                pytest.fail("Startup stole the writer's native ownership")
        assert prepared.read_bytes() == b"prepared update"
    with admission.acquire(root) if not cancel else installation_mutation(root):
        assert prepared.read_bytes() == b"prepared update"


def test_busy_mutation_owner_does_not_fall_back_to_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defer at the deadline instead of launching files owned by a current writer."""
    from collections.abc import Callable
    from concurrent.futures import ThreadPoolExecutor
    from launcher.sugarsubstitute_launcher import update_orchestrator
    from launcher.sugarsubstitute_launcher.application_startup_contract import (
        InstallationStartupDeferred,
    )
    from launcher.sugarsubstitute_launcher.startup_installation_wait import (
        StartupInstallationWait,
    )
    from sugarsubstitute_shared.installation_mutation import installation_mutation
    from launcher.sugarsubstitute_launcher.release_sources import (
        LocalFolderReleaseSource,
    )
    from launcher.sugarsubstitute_launcher.update_orchestrator import (
        LauncherUpdateOrchestrator,
    )

    now = [0.0]

    def advance(seconds: float) -> None:
        """Advance a controlled deadline while the native writer remains active."""
        now[0] += seconds

    def admission(
        *, cancellation_requested: Callable[[], bool] | None
    ) -> StartupInstallationWait:
        """Keep real kernel admission while binding a deterministic wait budget."""
        return StartupInstallationWait(
            timeout_seconds=0.1,
            monotonic=lambda: now[0],
            wait=advance,
            cancellation_requested=cancellation_requested,
        )

    monkeypatch.setattr(update_orchestrator, "StartupInstallationWait", admission)
    layout = InstallLayout.from_root(tmp_path / "install")
    config = LauncherConfig.from_layout(layout=layout)
    source = LocalFolderReleaseSource(tmp_path / "unread-release")
    with ThreadPoolExecutor(max_workers=1) as pool:
        with installation_mutation(layout.root):
            result = pool.submit(
                LauncherUpdateOrchestrator().run,
                layout=layout,
                config=config,
                release_source=source,
                no_update_check=False,
            )
            with pytest.raises(InstallationStartupDeferred):
                result.result(timeout=10)
    assert not layout.state_path.exists()
