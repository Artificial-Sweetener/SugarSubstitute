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

"""Prove new execution and fatal boundaries cannot bypass crash ownership."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.architecture_governance.crash_boundary_policy import (
    validate_crash_boundary_inventory,
    validate_crash_boundary_policy,
)
from tools.architecture_governance.loading import load_policy
from tools.architecture_governance.model import ArchitecturePolicy


_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _fixture_policy() -> ArchitecturePolicy:
    """Return a minimal policy governing one synthetic runtime package."""

    return ArchitecturePolicy(
        soft_lines=350,
        hard_lines=500,
        source_roots=(Path("substitute"),),
        source_files=(),
        source_extensions=frozenset({".py"}),
        excluded_paths=frozenset(),
        debt_registry=Path("ARCHITECTURE_DEBT.toml"),
        waiver_registry=Path("ARCHITECTURE_WAIVERS.toml"),
    )


@pytest.mark.parametrize(
    "source, primitive",
    [
        (
            "import subprocess\ndef bypass():\n    subprocess.Popen([])\n",
            "subprocess.Popen",
        ),
        (
            "import subprocess\ndef bypass():\n    subprocess.run([])\n",
            "subprocess.run",
        ),
        (
            "from multiprocessing import Process\ndef bypass():\n    Process()\n",
            "multiprocessing.Process",
        ),
        (
            "from PySide6.QtCore import QProcess\n"
            "def bypass():\n    QProcess.startDetached('app')\n",
            "PySide6.QtCore.QProcess.startDetached",
        ),
        (
            "import asyncio\n"
            "async def bypass():\n    await asyncio.create_subprocess_exec('app')\n",
            "asyncio.create_subprocess_exec",
        ),
        (
            "import os\ndef bypass():\n    os.execv('app', ['app'])\n",
            "os.execv",
        ),
        (
            "from threading import Thread\ndef bypass():\n    Thread()\n",
            "threading.Thread",
        ),
        (
            "from concurrent.futures import ThreadPoolExecutor\n"
            "def bypass():\n    ThreadPoolExecutor()\n",
            "concurrent.futures.ThreadPoolExecutor",
        ),
        (
            "from PySide6.QtCore import QThread\ndef bypass():\n    QThread()\n",
            "PySide6.QtCore.QThread",
        ),
        (
            "from PySide6.QtWidgets import QApplication\n"
            "def bypass():\n    QApplication([])\n",
            "PySide6.QtWidgets.QApplication",
        ),
        (
            "import asyncio\ndef bypass(work):\n    asyncio.create_task(work())\n",
            "asyncio.create_task",
        ),
        (
            "import asyncio\n"
            "def bypass(work):\n"
            "    loop = asyncio.get_running_loop()\n"
            "    loop.create_task(work())\n",
            "asyncio.AbstractEventLoop.create_task",
        ),
        (
            "import multiprocessing\n"
            "def bypass():\n"
            "    context = multiprocessing.get_context()\n"
            "    context.Process()\n",
            "multiprocessing.context.BaseContext.Process",
        ),
        (
            "from PySide6.QtCore import QThreadPool\n"
            "def bypass(work):\n"
            "    QThreadPool.globalInstance().start(work)\n",
            "PySide6.QtCore.QThreadPool.start",
        ),
        (
            "import sys\ndef bypass(handler):\n    sys.excepthook = handler\n",
            "sys.excepthook",
        ),
        (
            "from PySide6.QtCore import qInstallMessageHandler\n"
            "def bypass(handler):\n    qInstallMessageHandler(handler)\n",
            "PySide6.QtCore.qInstallMessageHandler",
        ),
        (
            "import faulthandler\ndef bypass():\n    faulthandler.disable()\n",
            "faulthandler.disable",
        ),
        ("import os\ndef bypass():\n    os.abort()\n", "os.abort"),
        ("def bypass():\n    raise SystemExit(2)\n", "builtins.SystemExit"),
    ],
)
def test_new_raw_boundary_fails_architecture(
    tmp_path: Path,
    source: str,
    primitive: str,
) -> None:
    """Every new primitive should require an explicit reviewed classification."""

    path = tmp_path / "substitute" / "bypass.py"
    path.parent.mkdir(parents=True)
    path.write_text(source, encoding="utf-8")

    diagnostics = validate_crash_boundary_policy(tmp_path, _fixture_policy())

    failure = next(item for item in diagnostics if item.rule == "CRASH001")
    assert failure.path == "substitute/bypass.py"
    assert primitive in failure.message
    assert "without an explicit crash-participation classification" in failure.message


def test_new_application_subclass_fails_architecture(tmp_path: Path) -> None:
    """Renaming a QApplication subclass must not evade application detection."""

    path = tmp_path / "substitute" / "bypass.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "from PySide6.QtWidgets import QApplication\n"
        "class UnmanagedApplication(QApplication):\n"
        "    pass\n",
        encoding="utf-8",
    )

    diagnostics = validate_crash_boundary_policy(tmp_path, _fixture_policy())

    failure = next(item for item in diagnostics if item.rule == "CRASH001")
    assert "application_class boundary" in failure.message
    assert "UnmanagedApplication" in failure.message


def test_new_thread_subclass_fails_architecture(tmp_path: Path) -> None:
    """Subclassing Thread must not evade construction-site detection."""

    path = tmp_path / "substitute" / "bypass.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "from threading import Thread\nclass UnmanagedThread(Thread):\n    pass\n",
        encoding="utf-8",
    )

    diagnostics = validate_crash_boundary_policy(tmp_path, _fixture_policy())

    failure = next(item for item in diagnostics if item.rule == "CRASH001")
    assert "thread_class boundary" in failure.message
    assert "UnmanagedThread" in failure.message


def test_inventory_rejects_bypass_dispositions_and_duplicate_sites() -> None:
    """Editing the allowlist must still use an approved participation contract."""

    row = (
        "application",
        "substitute/bypass.py",
        "main",
        "PySide6.QtWidgets.QApplication",
        1,
        "not_really_handled",
    )

    diagnostics = validate_crash_boundary_inventory((row, row))

    assert len(diagnostics) == 3
    assert all(diagnostic.rule == "CRASH003" for diagnostic in diagnostics)
    assert any("not an approved" in diagnostic.message for diagnostic in diagnostics)
    assert any("duplicate" in diagnostic.message for diagnostic in diagnostics)


def test_current_runtime_boundary_inventory_is_exact() -> None:
    """The production tree must have neither unreviewed nor stale boundary sites."""

    diagnostics = validate_crash_boundary_policy(
        _PROJECT_ROOT,
        load_policy(_PROJECT_ROOT / "ARCHITECTURE_POLICY.toml"),
    )

    assert diagnostics == []
