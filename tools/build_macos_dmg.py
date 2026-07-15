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

"""Build the public Apple Silicon DMG from the setup app bundle."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile


class MacosDmgBuildError(RuntimeError):
    """Report an invalid host, input bundle, or hdiutil build failure."""


def build_macos_dmg(*, setup_app: Path, output_path: Path) -> Path:
    """Create a compressed DMG containing setup and an Applications shortcut."""

    if platform.system() != "Darwin" or platform.machine().lower() not in {
        "arm64",
        "aarch64",
    }:
        raise MacosDmgBuildError(
            "The Apple Silicon installer DMG must be built on macOS arm64."
        )
    resolved_setup_app = setup_app.expanduser().resolve()
    resolved_output_path = output_path.expanduser().resolve()
    if not resolved_setup_app.is_dir() or resolved_setup_app.suffix != ".app":
        raise MacosDmgBuildError(f"Setup app bundle is missing: {resolved_setup_app}")

    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    if resolved_output_path.exists():
        resolved_output_path.unlink()
    with tempfile.TemporaryDirectory(prefix="sugarsubstitute-dmg-") as temporary_dir:
        staging_dir = Path(temporary_dir) / "SugarSubstitute Installer"
        staging_dir.mkdir()
        shutil.copytree(resolved_setup_app, staging_dir / resolved_setup_app.name)
        (staging_dir / "Applications").symlink_to(
            "/Applications", target_is_directory=True
        )
        try:
            subprocess.run(
                [
                    "hdiutil",
                    "create",
                    "-volname",
                    "SugarSubstitute Installer",
                    "-srcfolder",
                    str(staging_dir),
                    "-ov",
                    "-format",
                    "UDZO",
                    str(resolved_output_path),
                ],
                check=True,
                timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise MacosDmgBuildError(f"Failed to build macOS DMG: {error}") from error
    return resolved_output_path


def main() -> int:
    """Run the macOS DMG builder command-line interface."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup-app", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build_macos_dmg(setup_app=args.setup_app, output_path=args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
