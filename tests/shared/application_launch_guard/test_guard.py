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

"""Test installation-scoped application launch ownership."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import threading

from sugarsubstitute_shared.application_launch_guard import (
    APPLICATION_LAUNCH_TOKEN_ENV,
    ApplicationLaunchGuard,
    application_launch_install_root,
    application_launch_lock_path,
    clear_inherited_application_launch_token,
    inherited_application_launch_token,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_launch_guard_rejects_an_unrelated_live_launch(tmp_path: Path) -> None:
    """A live launch owner should prevent another launch from starting."""

    install_root = tmp_path / "SugarSubstitute"
    first = ApplicationLaunchGuard.enter(
        install_root,
        process_is_alive=lambda _pid: True,
        token_factory=lambda: "first-launch",
    )

    assert first is not None
    assert (
        ApplicationLaunchGuard.enter(
            install_root,
            process_is_alive=lambda _pid: True,
            token_factory=lambda: "unrelated-launch",
        )
        is None
    )

    first.release()


def test_launch_guard_allows_an_authorized_process_handoff(tmp_path: Path) -> None:
    """A child carrying the private launch token should claim the live launch."""

    install_root = tmp_path / "SugarSubstitute"
    launcher = ApplicationLaunchGuard.enter(
        install_root,
        process_is_alive=lambda _pid: True,
        token_factory=lambda: "launcher-handoff",
        allow_initial_handoff=True,
    )

    assert launcher is not None
    application = ApplicationLaunchGuard.enter(
        install_root,
        inherited_token=launcher.token,
        process_is_alive=lambda _pid: True,
    )
    assert application is not None
    assert (
        ApplicationLaunchGuard.enter(
            install_root,
            inherited_token=launcher.token,
            process_is_alive=lambda _pid: True,
        )
        is None
    )

    application.release()
    launcher.release()


def test_launch_guard_serializes_concurrent_handoff_claims(tmp_path: Path) -> None:
    """Concurrent children carrying one token must produce exactly one owner."""

    install_root = tmp_path / "SugarSubstitute"
    launcher = ApplicationLaunchGuard.enter(
        install_root,
        process_is_alive=lambda _pid: True,
        token_factory=lambda: "launcher-handoff",
        allow_initial_handoff=True,
    )
    worker_count = 8
    start_barrier = threading.Barrier(worker_count)

    assert launcher is not None

    def claim_handoff() -> ApplicationLaunchGuard | None:
        """Attempt one simultaneous claim of the launcher's handoff token."""

        start_barrier.wait()
        return ApplicationLaunchGuard.enter(
            install_root,
            inherited_token=launcher.token,
            process_is_alive=lambda _pid: True,
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        claims = list(executor.map(lambda _index: claim_handoff(), range(worker_count)))

    accepted_claims = [claim for claim in claims if claim is not None]
    assert len(accepted_claims) == 1

    accepted_claims[0].release()
    launcher.release()


def test_launch_guard_serializes_handoff_claims_across_processes(
    tmp_path: Path,
) -> None:
    """Separate Windows shortcut children must still produce only one app owner."""

    install_root = tmp_path / "SugarSubstitute"
    launcher = ApplicationLaunchGuard.enter(
        install_root,
        token_factory=lambda: "launcher-handoff",
        allow_initial_handoff=True,
    )
    child_script = (
        "import sys;"
        "from pathlib import Path;"
        "from sugarsubstitute_shared.application_launch_guard import "
        "ApplicationLaunchGuard,inherited_application_launch_token;"
        "guard=ApplicationLaunchGuard.enter("
        "Path(sys.argv[1]),"
        "inherited_token=inherited_application_launch_token());"
        "print('accepted' if guard is not None else 'rejected',flush=True)"
    )

    assert launcher is not None
    child_environment = launcher.initial_handoff_environment()
    children = [
        subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", child_script, str(install_root)],
            cwd=_REPOSITORY_ROOT,
            env=child_environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _index in range(4)
    ]
    try:
        child_results = [child.communicate(timeout=10.0) for child in children]
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5.0)

    assert [stdout.strip() for stdout, _stderr in child_results].count("accepted") == 1
    assert all(child.returncode == 0 for child in children)

    cleanup_guard = ApplicationLaunchGuard.enter(
        install_root,
        process_is_alive=lambda _pid: False,
        token_factory=lambda: "cleanup-launch",
    )
    assert cleanup_guard is not None
    cleanup_guard.release()
    launcher.release()


def test_launch_guard_never_reuses_a_consumed_token_for_a_dead_owner(
    tmp_path: Path,
) -> None:
    """A descendant must not revive consumed authority after its parent exits."""

    install_root = tmp_path / "SugarSubstitute"
    launcher = ApplicationLaunchGuard.enter(
        install_root,
        process_is_alive=lambda _pid: True,
        token_factory=lambda: "launcher-handoff",
        allow_initial_handoff=True,
    )

    assert launcher is not None
    application = ApplicationLaunchGuard.enter(
        install_root,
        inherited_token=launcher.token,
        process_is_alive=lambda _pid: True,
    )
    assert application is not None
    assert (
        ApplicationLaunchGuard.enter(
            install_root,
            inherited_token=launcher.token,
            process_is_alive=lambda _pid: False,
        )
        is None
    )

    application.release()
    launcher.release()


def test_launch_guard_rejects_a_second_launcher_before_initial_handoff(
    tmp_path: Path,
) -> None:
    """A pending application handoff must not authorize another launcher."""

    install_root = tmp_path / "SugarSubstitute"
    first_launcher = ApplicationLaunchGuard.enter(
        install_root,
        process_is_alive=lambda _pid: True,
        token_factory=lambda: "first-launcher",
        allow_initial_handoff=True,
    )

    assert first_launcher is not None
    assert (
        ApplicationLaunchGuard.enter(
            install_root,
            process_is_alive=lambda _pid: True,
            token_factory=lambda: "second-launcher",
            allow_initial_handoff=True,
        )
        is None
    )

    first_launcher.release()


def test_launch_guard_replaces_a_dead_owner(tmp_path: Path) -> None:
    """A stale lock should not permanently prevent future application launches."""

    install_root = tmp_path / "SugarSubstitute"
    stale = ApplicationLaunchGuard.enter(
        install_root,
        token_factory=lambda: "stale-launch",
    )

    assert stale is not None
    replacement = ApplicationLaunchGuard.enter(
        install_root,
        process_is_alive=lambda _pid: False,
        token_factory=lambda: "replacement-launch",
    )
    assert replacement is not None

    stale.release()
    assert application_launch_lock_path(install_root).is_file()
    replacement.release()
    assert not application_launch_lock_path(install_root).exists()


def test_launch_guard_fails_closed_for_a_malformed_lock(tmp_path: Path) -> None:
    """Unreadable ownership must not permit a duplicate application launch."""

    install_root = tmp_path / "SugarSubstitute"
    lock_path = application_launch_lock_path(install_root)
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("not-json", encoding="utf-8")

    assert ApplicationLaunchGuard.enter(install_root) is None


def test_launch_guard_builds_an_isolated_child_handoff_environment(
    tmp_path: Path,
) -> None:
    """Only the intended child environment should receive the private token."""

    guard = ApplicationLaunchGuard.enter(
        tmp_path / "SugarSubstitute",
        token_factory=lambda: "handoff-token",
        allow_initial_handoff=True,
    )
    parent_environment = {
        "PATH": "runtime",
        APPLICATION_LAUNCH_TOKEN_ENV: "unrelated-parent-token",
    }

    assert guard is not None
    child_environment = guard.initial_handoff_environment(parent_environment)
    assert parent_environment[APPLICATION_LAUNCH_TOKEN_ENV] == (
        "unrelated-parent-token"
    )
    assert child_environment == {
        "PATH": "runtime",
        APPLICATION_LAUNCH_TOKEN_ENV: "handoff-token",
    }
    assert inherited_application_launch_token(child_environment) == "handoff-token"

    guard.release()


def test_clear_inherited_application_launch_token_is_process_local() -> None:
    """Claimed startup authority should be removable before child creation."""

    environment = {
        "PATH": "runtime",
        APPLICATION_LAUNCH_TOKEN_ENV: "consumed-token",
    }

    clear_inherited_application_launch_token(environment)

    assert environment == {"PATH": "runtime"}


def test_launch_guard_allows_exactly_one_controlled_restart(tmp_path: Path) -> None:
    """A shutdown replacement should consume its dedicated one-use token."""

    install_root = tmp_path / "SugarSubstitute"
    application = ApplicationLaunchGuard.enter(
        install_root,
        token_factory=lambda: "running-application",
    )

    assert application is not None
    restart_environment = application.prepare_restart_environment()
    assert restart_environment is not None
    restart_token = restart_environment[APPLICATION_LAUNCH_TOKEN_ENV]
    replacement = ApplicationLaunchGuard.enter(
        install_root,
        inherited_token=restart_token,
        process_is_alive=lambda _pid: True,
    )

    assert replacement is not None
    assert (
        ApplicationLaunchGuard.enter(
            install_root,
            inherited_token=restart_token,
            process_is_alive=lambda _pid: True,
        )
        is None
    )

    replacement.release()
    application.release()


def test_launch_guard_revokes_a_restart_when_process_creation_fails(
    tmp_path: Path,
) -> None:
    """A failed spawn should restore authorization for one later restart attempt."""

    application = ApplicationLaunchGuard.enter(
        tmp_path / "SugarSubstitute",
        token_factory=lambda: "running-application",
    )

    assert application is not None
    failed_environment = application.prepare_restart_environment()
    assert failed_environment is not None

    application.cancel_restart_environment(failed_environment)

    retry_environment = application.prepare_restart_environment()
    assert retry_environment is not None
    assert (
        retry_environment[APPLICATION_LAUNCH_TOKEN_ENV]
        != (failed_environment[APPLICATION_LAUNCH_TOKEN_ENV])
    )

    application.release()


def test_application_launch_install_root_prefers_the_startup_argument(
    tmp_path: Path,
) -> None:
    """The installed app should share its launch lock with the launcher root."""

    app_root = tmp_path / "app"
    install_root = tmp_path / "installed"

    assert (
        application_launch_install_root(
            ["main.py", f"--install-root={install_root}"],
            app_root=app_root,
        )
        == install_root.resolve()
    )
