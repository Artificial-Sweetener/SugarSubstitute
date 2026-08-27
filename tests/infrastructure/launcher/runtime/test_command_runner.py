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

"""Qualify launcher subprocess output, failure evidence, and redaction."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.runtime_command import (
    SubprocessRuntimeCommandRunner,
)


def test_subprocess_runtime_runner_streams_output_without_shell(
    tmp_path: Path,
) -> None:
    """Runtime command output is capturable for the graphical installer log."""

    output_lines: list[str] = []

    SubprocessRuntimeCommandRunner(output_lines.append).run(
        [sys.executable, "-c", "print('runtime line')"],
        cwd=tmp_path,
        env=os.environ,
    )

    assert output_lines == ["runtime line"]


def test_subprocess_runtime_runner_replaces_invalid_output_bytes(
    tmp_path: Path,
) -> None:
    """Runtime command output decoding never depends on the Windows ANSI code page."""

    output_lines: list[str] = []

    SubprocessRuntimeCommandRunner(output_lines.append).run(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'bad\\x90byte\\n')",
        ],
        cwd=tmp_path,
        env=os.environ,
    )

    assert output_lines == ["bad\ufffdbyte"]


def test_subprocess_runtime_runner_logs_captured_failure_output(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failed runtime commands should preserve their output in launcher logs."""

    with caplog.at_level(
        logging.INFO,
        logger="launcher.sugarsubstitute_launcher.runtime_command",
    ):
        with pytest.raises(subprocess.CalledProcessError) as error_info:
            SubprocessRuntimeCommandRunner().run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; "
                        "print('runtime failure detail token=private-value'); "
                        "raise SystemExit(7)"
                    ),
                ],
                cwd=tmp_path,
                env=os.environ,
            )

    assert error_info.value.returncode == 7
    assert error_info.value.output == "runtime failure detail token=private-value"
    assert "runtime failure detail" in caplog.text
    assert "private-value" not in caplog.text
    assert "token=<redacted>" in caplog.text
    assert "return_code=7" in caplog.text


def test_subprocess_runtime_runner_redacts_supported_credential_forms(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Persisted failure output should redact URL, assignment, and bearer secrets."""

    script = (
        "print('https://alice:hunter2@example.com/path "
        "password=private-password "
        "Authorization=private-authorization "
        "Bearer private-bearer'); "
        "raise SystemExit(8)"
    )
    with caplog.at_level(
        logging.INFO,
        logger="launcher.sugarsubstitute_launcher.runtime_command",
    ):
        with pytest.raises(subprocess.CalledProcessError):
            SubprocessRuntimeCommandRunner().run(
                [sys.executable, "-c", script],
                cwd=tmp_path,
                env=os.environ,
            )

    assert "hunter2" not in caplog.text
    assert "private-password" not in caplog.text
    assert "private-authorization" not in caplog.text
    assert "private-bearer" not in caplog.text
    assert "https://<redacted>@example.com/path" in caplog.text
    assert "password=<redacted>" in caplog.text
    assert "Authorization=<redacted>" in caplog.text
    assert "Bearer <redacted>" in caplog.text
