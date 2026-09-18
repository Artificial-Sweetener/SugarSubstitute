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

"""Exit an isolated updater at its first directory-copy boundary."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys

from sugarsubstitute_shared.launcher_update.transaction import LauncherUpdateTransaction


def main() -> None:
    """Interrupt only this fixture process before a directory payload is copied."""
    request_path = Path(sys.argv[1])

    def interrupt_copy(*args: object, **kwargs: object) -> str:
        """Model abrupt death without entering the transaction's exception handler."""
        os._exit(73)

    shutil.copytree = interrupt_copy  # type: ignore[assignment]
    LauncherUpdateTransaction().apply(request_path=request_path)
    raise AssertionError("The update never reached directory publication.")


if __name__ == "__main__":
    main()
