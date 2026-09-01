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

"""Verify authorized app restarts remain beneath full crash supervision."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher import restart_supervision
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_launch_guard import (
    APPLICATION_LAUNCH_TOKEN_ENV,
)
from sugarsubstitute_shared.application_runtime_mode import (
    APPLICATION_RUNTIME_MODE_ENV,
    PACKAGED_APPLICATION_RUNTIME_MODE,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path


def test_restart_mode_passes_one_use_token_to_supervised_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The stable launcher should adopt the token and own the app lifetime."""

    layout = InstallLayout.from_root(tmp_path / "install")
    calls: list[dict[str, object]] = []

    class _RecordingSupervisor:
        """Record one restart supervision request."""

        def supervise(self, **kwargs: object) -> int:
            """Capture the child contract and return its exit status."""

            calls.append(kwargs)
            return 17

    monkeypatch.setenv(APPLICATION_LAUNCH_TOKEN_ENV, "restart-token")
    monkeypatch.setattr(
        restart_supervision,
        "ApplicationCrashSupervisor",
        _RecordingSupervisor,
    )

    assert restart_supervision.supervise_restarted_application(layout=layout) == 17

    assert calls[0]["layout"] == layout
    assert calls[0]["command"] == [
        subprocess_path(layout.runtime_python),
        subprocess_path(layout.app_entrypoint),
        f"--install-root={subprocess_path(layout.root)}",
    ]
    environment = calls[0]["environment"]
    assert isinstance(environment, dict)
    assert environment[APPLICATION_LAUNCH_TOKEN_ENV] == "restart-token"
    assert (
        environment[APPLICATION_RUNTIME_MODE_ENV] == PACKAGED_APPLICATION_RUNTIME_MODE
    )
    assert APPLICATION_LAUNCH_TOKEN_ENV not in os.environ


def test_restart_mode_rejects_missing_handoff_authority(tmp_path: Path) -> None:
    """A standalone internal restart invocation must fail before app launch."""

    layout = InstallLayout.from_root(tmp_path / "install")

    with pytest.raises(RuntimeError, match="handoff token"):
        restart_supervision.supervise_restarted_application(layout=layout)
