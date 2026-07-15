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

"""Tests for POSIX guardian managed ComfyUI containment."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import cast

import pytest

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy import posix_guardian_containment
from substitute.infrastructure.comfy.posix_guardian_containment import (
    PosixGuardianContainmentHandle,
)
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedContainmentError,
    build_launch_request,
)

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="POSIX guardian integration coverage runs on Linux.",
)


def test_guardian_launch_reports_child_pid_and_process_group(tmp_path: Path) -> None:
    """POSIX launch should return guardian, child, and process-group ownership."""

    result = posix_guardian_containment.launch_with_guardian(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path,
        request=build_launch_request(
            command=(
                sys.executable,
                "-c",
                "import time; time.sleep(300)",
            ),
            cwd=tmp_path,
            env=os.environ.copy(),
            capture_output=False,
        ),
    )
    metadata = result.metadata

    try:
        assert metadata.containment_mode == "posix_guardian"
        assert metadata.owner_pid is not None
        assert metadata.process_group_id is not None
        assert metadata.pid > 0
    finally:
        posix_guardian_containment.request_guardian_stop(
            cast(PosixGuardianContainmentHandle, result.containment_handle)
        )


def test_guardian_launch_surfaces_handshake_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Invalid guardian control payloads should surface a typed containment error."""

    class _BadStdout:
        """Return one invalid JSON line for deterministic handshake failure coverage."""

        def readline(self) -> bytes:
            """Return one invalid control payload."""

            return b"[]\n"

    class _FakeGuardianProcess:
        """Provide the minimal guardian process surface used during handshake tests."""

        pid = 200
        stdin = None
        stdout = _BadStdout()
        stderr = None

        def kill(self) -> None:
            """Provide the no-op kill surface used by launch cleanup."""

            return None

        def poll(self) -> int | None:
            """Behave like a still-running process until launch fails."""

            return None

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.posix_guardian_containment.subprocess.Popen",
        lambda *args, **kwargs: _FakeGuardianProcess(),
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.posix_guardian_containment.os.pipe",
        lambda: (10, 11),
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.posix_guardian_containment.os.set_inheritable",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.posix_guardian_containment.os.close",
        lambda _fd: None,
    )

    with pytest.raises(ManagedContainmentError, match="non-object payload"):
        posix_guardian_containment.launch_with_guardian(
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace=tmp_path,
            request=build_launch_request(
                command=("python", "main.py"),
                cwd=tmp_path,
                env={"PATH": "test"},
                capture_output=False,
            ),
        )
