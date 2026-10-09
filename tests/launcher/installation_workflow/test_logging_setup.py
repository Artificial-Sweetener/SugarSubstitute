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

"""Verify durable launcher identity publication and nonfatal capture failures."""

from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
import json
import logging
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher import logging_setup
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.logging_setup import configure_launcher_logging
from launcher.sugarsubstitute_launcher.process_identity_evidence import (
    LAUNCHER_PROCESS_EVENT,
    LauncherProcessEvidence,
)
from sugarsubstitute_shared.windows_long_paths import logical_path
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    ProcessIdentityError,
)


@pytest.fixture
def launcher_log_root() -> Generator[logging.Logger, None, None]:
    """Close added file handlers and restore the process-wide logging level."""
    root = logging.getLogger()
    handlers = tuple(root.handlers)
    level = root.level
    try:
        yield root
    finally:
        for handler in tuple(root.handlers):
            if handler not in handlers:
                root.removeHandler(handler)
                handler.close()
        root.setLevel(level)


def test_logging_publishes_identity_once_during_repeated_or_racing_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    launcher_log_root: logging.Logger,
) -> None:
    """The first handler emits one atomic ancestry record before application logs."""
    del launcher_log_root
    image = str(tmp_path / "SugarSubstitute")
    evidence = LauncherProcessEvidence(
        identity=ProcessIdentity(421, 123.5),
        parent_identity=ProcessIdentity(420, 123.25),
        executable=image,
        parent_executable=image,
    )
    captures: list[LauncherProcessEvidence] = []

    def capture() -> LauncherProcessEvidence:
        """Observe capture count without depending on the test runner's ancestry."""
        captures.append(evidence)
        return evidence

    monkeypatch.setattr(logging_setup, "capture_launcher_process_evidence", capture)
    layout = InstallLayout.from_root(tmp_path / "installation")

    def configure(_request: int) -> Path:
        """Initialize the same installation from concurrent callers."""
        return configure_launcher_logging(layout=layout)

    with ThreadPoolExecutor(max_workers=4) as executor:
        paths = tuple(executor.map(configure, range(8)))
    logging.getLogger(__name__).info("After launcher logging setup")
    lines = paths[0].read_text(encoding="utf-8").splitlines()

    assert len(set(paths)) == 1
    assert captures == [evidence]
    assert len(lines) == 2
    assert LAUNCHER_PROCESS_EVENT in lines[0]
    assert (
        LauncherProcessEvidence.from_json(
            json.loads(lines[0].split(LAUNCHER_PROCESS_EVENT, 1)[1])
        )
        == evidence
    )
    assert "After launcher logging setup" in lines[1]


def test_logging_capture_failure_warns_once_and_does_not_block_startup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    launcher_log_root: logging.Logger,
) -> None:
    """Leave qualification without evidence while ordinary logging remains usable."""
    del launcher_log_root

    def fail_capture() -> LauncherProcessEvidence:
        """Represent an inaccessible parent without substituting a PID-only record."""
        raise ProcessIdentityError("Parent process executable is inaccessible")

    monkeypatch.setattr(
        logging_setup, "capture_launcher_process_evidence", fail_capture
    )
    layout = InstallLayout.from_root(tmp_path / "installation")

    log_path = configure_launcher_logging(layout=layout)
    configure_launcher_logging(layout=layout)
    logging.getLogger(__name__).info("Application startup continued")
    content = log_path.read_text(encoding="utf-8")

    assert content.count("Launcher process identity capture failed") == 1
    assert "WARNING" in content
    assert "Parent process executable is inaccessible" in content
    assert "Application startup continued" in content
    assert LAUNCHER_PROCESS_EVENT not in content


def test_launcher_logging_writes_under_launcher_logs(
    tmp_path: Path,
    launcher_log_root: logging.Logger,
) -> None:
    """Create launcher logs beneath launcher-owned state."""
    del launcher_log_root

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    log_path = configure_launcher_logging(layout=layout)

    assert log_path == layout.logs_dir / "launcher.log"
    assert log_path.parent.is_dir()


def test_launcher_logging_collapses_duplicate_handlers_for_the_same_file(
    tmp_path: Path,
    launcher_log_root: logging.Logger,
) -> None:
    """Repeated or racing setup must never duplicate each diagnostic event."""
    del launcher_log_root

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    log_path = configure_launcher_logging(layout=layout)
    duplicate = logging.FileHandler(log_path, encoding="utf-8")
    root_logger = logging.getLogger()
    root_logger.addHandler(duplicate)
    try:
        configure_launcher_logging(layout=layout)
        matching = [
            handler
            for handler in root_logger.handlers
            if isinstance(handler, logging.FileHandler)
            and Path(logical_path(handler.baseFilename)).resolve() == log_path.resolve()
        ]

        assert len(matching) == 1
    finally:
        for handler in tuple(root_logger.handlers):
            if isinstance(handler, logging.FileHandler) and (
                Path(logical_path(handler.baseFilename)).resolve() == log_path.resolve()
            ):
                root_logger.removeHandler(handler)
                handler.close()
