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

"""Own installer visual-resource locations across source and packaged runtimes."""

from __future__ import annotations

from pathlib import Path
import sys


INSTALLER_WORDMARK_SOURCE_RELATIVE_PATH = Path("docs/readme/sugarsubstitute-logo.svg")
INSTALLER_WORDMARK_RUNTIME_RELATIVE_PATH = Path(
    "sugarsubstitute_shared/presentation/resources/sugarsubstitute-logo.svg"
)


def installer_wordmark_path() -> Path:
    """Resolve the wordmark from a frozen launcher, app payload, or checkout."""

    packaged_path = (
        Path(getattr(sys, "_MEIPASS", ""))
        / "launcher_assets"
        / INSTALLER_WORDMARK_SOURCE_RELATIVE_PATH.name
    )
    runtime_path = (
        Path(__file__).resolve().parents[2] / INSTALLER_WORDMARK_RUNTIME_RELATIVE_PATH
    )
    source_path = (
        Path(__file__).resolve().parents[2] / INSTALLER_WORDMARK_SOURCE_RELATIVE_PATH
    )
    for candidate in (packaged_path, runtime_path, source_path):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Installer wordmark is missing: {runtime_path}")


__all__ = [
    "INSTALLER_WORDMARK_RUNTIME_RELATIVE_PATH",
    "INSTALLER_WORDMARK_SOURCE_RELATIVE_PATH",
    "installer_wordmark_path",
]
