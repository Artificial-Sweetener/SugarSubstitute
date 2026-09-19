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

"""Verify splash readiness while a native helper fills its diagnostic pipe."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import sys

import pytest
import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.splash_session import (
    start_launcher_splash_session,
)
from sugarsubstitute_shared.supervised_text_process import (
    SupervisedTextProcess,
    start_supervised_text_process,
)

pytestmark = pytest.mark.platforms("windows")


def test_diagnostic_backpressure_cannot_block_splash_readiness(tmp_path: Path) -> None:
    """Drain real stderr before the helper can publish its ready message."""
    processes: list[SupervisedTextProcess] = []
    script = (
        "import json, os, sys; from threading import Event; "
        "sys.stderr.write('diagnostic\\n' * 100000); sys.stderr.flush(); "
        "print(json.dumps(dict(type='ready', endpoint='127.0.0.1:1', "
        "token='x'*32, host_pid=os.getpid())), flush=True); Event().wait(30)"
    )

    def start_fixture(
        command: Sequence[str], *, environment: Mapping[str, str], cwd: Path
    ) -> SupervisedTextProcess:
        """Replace the GUI payload with a hidden diagnostic-producing process."""
        del command
        process = start_supervised_text_process(
            [sys.executable, "-c", script], environment=environment, cwd=cwd
        )
        processes.append(process)
        return process

    try:
        session = start_launcher_splash_session(
            layout=InstallLayout.from_root(tmp_path),
            locale_override=None,
            process_starter=start_fixture,
        )
        assert session is not None, "Diagnostic output prevented readiness"
        owner = psutil.Process(processes[0].pid)
        family = [owner, *owner.children(recursive=True)]
        assert session.host_pid in {process.pid for process in family}
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
