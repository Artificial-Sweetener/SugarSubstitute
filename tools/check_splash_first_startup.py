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

"""Enforce splash-first startup across executable entrypoints."""

from __future__ import annotations

from pathlib import Path

from tools.splash_first_governance import validate_repository


def main() -> int:
    """Print splash-first diagnostics and return the repository gate status."""

    repository_root = Path(__file__).resolve().parents[1]
    diagnostics = validate_repository(repository_root)
    for diagnostic in diagnostics:
        relative_path = diagnostic.path.relative_to(repository_root)
        print(
            f"{relative_path}:{diagnostic.line}: error {diagnostic.code}: "
            f"{diagnostic.message}"
        )
    if diagnostics:
        print(f"FAILED: Found {len(diagnostics)} splash-first startup violation(s).")
        return 1
    print("Splash-first startup contracts passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
