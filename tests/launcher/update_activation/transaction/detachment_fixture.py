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

"""Exercise updater admission inside a real native parent job."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from sugarsubstitute_shared.launcher_update.process import schedule_launcher_update


def main() -> None:
    """Report whether a supposedly independent updater was admitted."""
    root = Path(sys.argv[1])
    try:
        pid = schedule_launcher_update(
            request_path=root / "SugarSubstitute/launcher/updates/pending.json",
            runtime_python=Path(sys.executable),
            app_dir=root / "SugarSubstitute/app",
            relaunch=False,
            wait_pid=os.getpid(),
        )
        result: dict[str, object] = {"admitted": True, "pid": pid}
    except OSError as error:
        result = {"admitted": False, "reason": str(error)}
    (root / "admission.json").write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()
