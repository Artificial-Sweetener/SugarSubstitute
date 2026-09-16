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

"""Keep startup feedback available after a generation closes the inherited splash."""

from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher import (
    app,
    application_launch,
    generation_dispatch,
    installed_app_handoff,
    splash_session,
)
from tests.launcher.application_launch.instance_routing_support import (
    BrokerDouble,
    installed_layout,
)


def test_generation_fallback_replaces_closed_splash_under_same_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recreate feedback before baseline handoff without another owner election."""
    layout = installed_layout(tmp_path)
    owner = BrokerDouble()
    elections: list[bool] = []

    class Surface:
        """Represent presentation lifetime without a window or process."""

        def __init__(self) -> None:
            """Start a live fixture surface."""
            self.closed = False

        def present(self) -> str | None:
            """Report whether the fixture can still provide feedback."""
            return None if self.closed else "startup-splash"

        def close(self) -> None:
            """Close idempotently as a real owned splash does."""
            self.closed = True

    surfaces: list[Surface] = []

    def start(**_kwargs: object) -> Surface:
        """Record each newly created startup surface."""
        surface = Surface()
        surfaces.append(surface)
        return surface

    def elect(*_args: object) -> BrokerDouble:
        """Retain the same native-owner boundary through fallback."""
        elections.append(True)
        return owner

    def dispatch(**kwargs: object) -> None:
        """Model a generation requesting restart after it closed the inherited surface."""
        assert kwargs["splash_session"] is surfaces[0]
        surfaces[0].close()
        resume = kwargs["on_baseline_fallback"]
        assert callable(resume)
        resume()

    def handoff(**kwargs: object) -> None:
        """Require fresh feedback and the original owner before app startup resumes."""
        assert len(surfaces) == 2
        assert kwargs["splash_session"] is surfaces[1]
        assert surfaces[1].present() == "startup-splash"
        assert kwargs["broker"] is owner

    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(application_launch, "elect_application", elect)
    monkeypatch.setattr(splash_session, "start_launcher_splash_session", start)
    monkeypatch.setattr(generation_dispatch, "dispatch_selected_launcher", dispatch)
    monkeypatch.setattr(
        installed_app_handoff, "complete_installed_app_handoff", handoff
    )
    assert app.main([]) == 0
    assert elections == [True]
    assert owner.closed
