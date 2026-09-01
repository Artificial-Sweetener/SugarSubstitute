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

"""Verify direct source execution becomes a full-lifetime supervised child."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Self

import pytest

from launcher.sugarsubstitute_launcher import source_crash_supervision
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.windows_long_paths import subprocess_path


def test_source_launch_restarts_itself_under_crashpad_supervisor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The first source process should supervise, not run the app directly."""

    app_root = tmp_path / "source"
    app_root.mkdir()
    (app_root / "main.py").touch()
    calls: list[dict[str, object]] = []
    native_paths: list[tuple[Path, Path]] = []

    class _RecordingSupervisor:
        """Record source supervision configuration and launch arguments."""

        def __init__(self, **kwargs: object) -> None:
            """Capture the source-native resolver before launch."""

            resolver = kwargs["native_runtime_resolver"]
            assert callable(resolver)
            layout = InstallLayout.from_root(app_root)
            native_paths.append(resolver(layout))

        def supervise(self, **kwargs: object) -> int:
            """Record the supervised source child."""

            calls.append(kwargs)
            return 23

    class _Broker:
        """Represent the elected source supervisor without opening real IPC."""

        def child_environment(self, environment: object) -> dict[str, str]:
            """Return one isolated marker environment."""

            _ = environment
            return {"TEST_INSTANCE_BROKER": "connected"}

        def consume_restart_request(self) -> bool:
            """Finish after the first recorded child."""

            return False

        def __enter__(self) -> Self:
            """Retain election through the recorded child lifetime."""

            return self

        def __exit__(self, *_exc_info: object) -> None:
            """Release the fake election."""

    monkeypatch.setattr(
        ApplicationInstanceBroker,
        "elect",
        lambda **_kwargs: _Broker(),
    )

    monkeypatch.setattr(
        source_crash_supervision,
        "ApplicationCrashSupervisor",
        _RecordingSupervisor,
    )

    assert (
        source_crash_supervision.supervise_source_application(
            argv=[str(app_root / "main.py"), "--locale=ja"],
            app_root=app_root,
        )
        == 23
    )

    assert calls[0]["command"] == [
        subprocess_path(Path(sys.executable)),
        subprocess_path(app_root / "main.py"),
        "--locale=ja",
    ]
    assert calls[0]["environment"] == {"TEST_INSTANCE_BROKER": "connected"}
    layout = calls[0]["layout"]
    assert isinstance(layout, InstallLayout)
    target_root = (
        app_root
        / "third_party"
        / "bin"
        / "crashpad"
        / layout.target.key.replace("_", "-")
    )
    assert native_paths == [
        (
            target_root / layout.crashpad_handler_path.name,
            target_root / layout.crashpad_client_library_path.name,
        )
    ]
