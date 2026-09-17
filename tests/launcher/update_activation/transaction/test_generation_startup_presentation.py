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

"""Keep splash activation available while a delegated app replaces its channel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import sys
from threading import Event

import pytest

from launcher.sugarsubstitute_launcher.generation_dispatch import (
    dispatch_selected_launcher,
)
from launcher.sugarsubstitute_launcher.delegated_startup_presentation import (
    DelegatedStartupPresentation,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher.splash_transfer import (
    take_borrowed_splash_session,
)
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInvocation,
    RoutedApplicationInvocation,
)
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)
from sugarsubstitute_shared.delegated_application_broker import (
    DelegatedApplicationBroker,
)
from sugarsubstitute_shared.launch_splash.client import SocketSplashSessionClient
from sugarsubstitute_shared.launch_splash.session import (
    create_splash_session_spec,
    splash_session_args,
)
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from .support import _write_bundle_tree, _write_installed_layout


class SplashSurface:
    """Replace only the external painted surface, retaining real broker routing."""

    def __init__(self) -> None:
        """Retain one transferred surface identity and observable lifecycle."""
        self.client = SocketSplashSessionClient(create_splash_session_spec(port=12345))
        self.presentations = 0
        self.closed = False

    @property
    def app_arguments(self) -> tuple[str, ...]:
        """Expose the normal transfer contract without starting a Qt host."""
        return tuple(splash_session_args(self.client.spec))

    def present(self) -> str | None:
        """Acknowledge only a live startup surface."""
        if self.closed:
            return None
        self.presentations += 1
        return "startup-splash"

    def cancellation_requested(self) -> bool:
        """Keep this deterministic startup active until the test releases it."""
        return False

    def ensure_closed(self) -> None:
        """Retire the external surface once the app owns presentation."""
        self.closed = True

    def close(self) -> None:
        """Apply the same idempotent surface release."""
        self.ensure_closed()


def test_registered_starting_app_does_not_hide_delegated_splash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Present the splash until readiness, then deliver retained intent to the app."""
    root = _write_installed_layout(tmp_path / "installation")
    staged = root / "launcher/updates/staged"
    _write_bundle_tree(staged, marker="candidate")
    assets = staged / "launcher-bin/launcher_assets"
    assets.mkdir()
    (assets / "launcher-contract.json").write_text(
        '{"schema_version": 1, "delegation_protocol": 1}'
    )
    selection = LauncherBundleSelection(root, WINDOWS_X64_BUNDLE)
    selection.activate(selection.publish(staged, version="1"))
    layout = InstallLayout.from_root(root, target=WINDOWS_X64)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    owner = ApplicationInstanceBroker.elect(
        install_root=root, invocation=ApplicationInvocation.capture(["launcher"])
    )
    assert owner is not None
    splash = SplashSurface()

    class StartingGeneration:
        """Exercise both real child registrations before any main-window readiness."""

        def supervise(
            self,
            *,
            layout: InstallLayout,
            command: Sequence[str],
            environment: Mapping[str, str],
        ) -> int:
            """Replace delegated startup registration with an app still initializing."""
            delegate = DelegatedApplicationBroker(environment)
            delegate.bind_startup_presenter(lambda _: splash.present())
            app = ApplicationSupervisorClient.connect_from_environment(
                dict(environment)
            )
            assert app is not None
            delivered = Event()

            def present(request: RoutedApplicationInvocation) -> None:
                """Complete retained work after the app is ready to present it."""
                app.complete_invocation(
                    request.request_id, outcome="presented", surface="main-shell"
                )
                delivered.set()

            try:
                assert (
                    ApplicationInstanceBroker.elect(
                        install_root=root,
                        invocation=ApplicationInvocation.capture(["second-launch"]),
                    )
                    is None
                )
                assert splash.presentations >= 1
                app.bind_invocation_handler(present)
                assert delivered.wait(5), (
                    "Startup activation lost the invocation's app work"
                )
                borrowed = take_borrowed_splash_session(
                    dict(environment), release=delegate.release_startup_resource
                )
                assert borrowed is not None
                borrowed.ensure_closed()
                assert splash.closed
                count = splash.presentations
                assert (
                    ApplicationInstanceBroker.elect(
                        install_root=root,
                        invocation=ApplicationInvocation.capture(["warm-launch"]),
                    )
                    is None
                )
                assert splash.presentations == count
                return 0
            finally:
                app.close()
                delegate.close()

    with owner:
        assert (
            dispatch_selected_launcher(
                layout=layout,
                broker=owner,
                arguments=(),
                supervisor=StartingGeneration(),
                splash_session=splash,
                register_startup_resource=owner.register_startup_resource,
            )
            == 0
        )


def test_late_splash_release_preserves_fallback_presentation(tmp_path: Path) -> None:
    """Keep the replacement surface available when old startup cleanup arrives late."""
    owner = ApplicationInstanceBroker.elect(
        install_root=tmp_path,
        invocation=ApplicationInvocation.capture(["launcher"]),
    )
    assert owner is not None
    splash = SplashSurface()
    replacement_presented = Event()

    def present_replacement(invocation: ApplicationInvocation) -> str:
        """Acknowledge activation through the replacement startup surface."""
        replacement_presented.set()
        return "replacement-splash"

    with owner:
        with DelegatedStartupPresentation(
            broker=owner,
            splash=splash,
            register_resource=owner.register_startup_resource,
        ) as environment:
            delegate = DelegatedApplicationBroker(owner.child_environment(environment))
            borrowed = take_borrowed_splash_session(
                dict(environment), release=delegate.release_startup_resource
            )
            assert borrowed is not None
        try:
            owner.bind_startup_presenter(present_replacement)
            borrowed.ensure_closed()
            assert splash.closed
            assert (
                ApplicationInstanceBroker.elect(
                    install_root=tmp_path,
                    invocation=ApplicationInvocation.capture(["repeat-launch"]),
                )
                is None
            )
            assert replacement_presented.is_set()
        finally:
            delegate.close()
