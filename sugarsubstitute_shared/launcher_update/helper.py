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

"""Run launcher replacement from the independently managed app runtime."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

from sugarsubstitute_shared.launcher_update.transaction import (
    LauncherUpdateTransaction,
)


def main(argv: list[str] | None = None) -> int:
    """Apply the single pending update request named on the command line."""

    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        raise SystemExit("usage: launcher-update-helper REQUEST_PATH")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    request_path = Path(arguments[0]).expanduser().resolve()
    LauncherUpdateTransaction().apply(request_path=request_path)
    logging.getLogger(__name__).info(
        "Launcher update completed | request_path=%s",
        request_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
