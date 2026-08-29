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

"""Verify operating-system lifetime ownership for one application instance."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from sugarsubstitute_shared.application_instance_lease import ApplicationInstanceLease


def test_lease_allows_exactly_one_live_owner(tmp_path: Path) -> None:
    """A second process handle must not acquire a live installation lease."""

    install_root = tmp_path / "SugarSubstitute"
    first = ApplicationInstanceLease.acquire(install_root)

    assert first is not None
    assert ApplicationInstanceLease.acquire(install_root) is None

    first.release()
    replacement = ApplicationInstanceLease.acquire(install_root)
    assert replacement is not None
    replacement.release()


def test_lease_is_released_automatically_after_process_crash(tmp_path: Path) -> None:
    """The operating system must recover ownership after an ungraceful exit."""

    install_root = tmp_path / "SugarSubstitute"
    script = (
        "import os,sys;from pathlib import Path;"
        "from sugarsubstitute_shared.application_instance_lease import "
        "ApplicationInstanceLease;"
        "lease=ApplicationInstanceLease.acquire(Path(sys.argv[1]));"
        "print('acquired' if lease else 'rejected',flush=True);os._exit(7)"
    )
    process = subprocess.run(
        [sys.executable, "-c", script, str(install_root)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert process.returncode == 7
    assert process.stdout.strip() == "acquired"
    replacement = ApplicationInstanceLease.acquire(install_root)
    assert replacement is not None
    replacement.release()
