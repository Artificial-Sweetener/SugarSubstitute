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

"""Provide shared application-instance routing test fixtures."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tests.launcher.support import write_launcher_executable


class BrokerDouble:
    """Provide deterministic broker behavior for launcher orchestration tests."""

    def __init__(self) -> None:
        """Start as an open primary without a restart request."""

        self.closed = False
        self.startup_presenters: list[object] = []

    def child_environment(self, environment: Mapping[str, str]) -> dict[str, str]:
        """Mark the environment as authorized by this fake supervisor."""

        child = dict(environment)
        child["TEST_INSTANCE_BROKER"] = "connected"
        return child

    def register_startup_resource(self, cleanup: Callable[[], None]) -> str:
        """Reject unexpected generation transfer in an orchestration-only fixture."""
        raise AssertionError("This fixture does not launch a frozen generation.")

    def release_startup_resource(self, identity: str) -> None:
        """Reject unexpected borrowed cleanup in an orchestration-only fixture."""
        raise AssertionError("This fixture does not own a borrowed splash.")

    def consume_restart_request(self) -> bool:
        """Report no restart request for the recorded initial run."""

        return False

    def close(self) -> None:
        """Record release of supervisor ownership."""

        self.closed = True

    def bind_startup_presenter(self, presenter: object) -> None:
        """Accept the startup presenter used by the installed launch path."""

        self.startup_presenters.append(presenter)


def installed_layout(tmp_path: Path) -> InstallLayout:
    """Create the minimum launchable installed layout."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout, release_source=None).save(
        layout.config_path
    )
    write_launcher_executable(layout)
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_text("", encoding="utf-8")
    return layout


__all__ = ["BrokerDouble", "installed_layout"]
