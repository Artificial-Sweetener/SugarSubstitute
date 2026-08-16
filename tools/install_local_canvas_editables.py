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

"""Install and validate the local Ferrastra, QPane, and CuteCanvas overlay."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CANVAS_ROOT = _REPOSITORY_ROOT.parent / "CuteCanvas"

CommandRunner = Callable[[Sequence[str]], None]


def install_local_canvas_editables(
    *,
    python_executable: Path,
    canvas_root: Path,
    runner: CommandRunner | None = None,
) -> None:
    """Install the canvas-stack editables and verify their resolved source roots.

    Args:
        python_executable: Interpreter of the target virtual environment.
        canvas_root: Local canvas monorepo root containing all package roots.
        runner: Subprocess boundary used for deterministic automation tests.

    Raises:
        FileNotFoundError: If the local canvas package roots are unavailable.
        subprocess.CalledProcessError: If installation or validation fails.
    """

    ferrastra_package, qpane_package, cutecanvas_package = local_canvas_package_roots(
        canvas_root
    )
    python = str(Path(python_executable).resolve())
    execute = runner or _run_command
    execute(
        (
            python,
            "-m",
            "pip",
            "install",
            *_non_canvas_runtime_requirements(_REPOSITORY_ROOT / "requirements.txt"),
        )
    )
    for package in (ferrastra_package, qpane_package):
        execute(
            (
                python,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--editable",
                str(package),
            )
        )
    execute(
        (
            python,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--editable",
            f"{cutecanvas_package}[sam]",
        )
    )
    execute(
        (
            python,
            "-c",
            _validation_script(
                ferrastra_package,
                qpane_package,
                cutecanvas_package,
            ),
        )
    )


def local_canvas_package_roots(canvas_root: Path) -> tuple[Path, Path, Path]:
    """Return validated package roots for one canvas-stack checkout."""

    root = Path(canvas_root).resolve()
    ferrastra_package = root / "packages" / "ferrastra"
    qpane_package = root / "packages" / "qpane"
    cutecanvas_package = root / "packages" / "cutecanvas"
    for package in (ferrastra_package, qpane_package, cutecanvas_package):
        if not (package / "pyproject.toml").is_file():
            raise FileNotFoundError(f"Local canvas package is unavailable: {package}")
    return ferrastra_package, qpane_package, cutecanvas_package


def _non_canvas_runtime_requirements(requirements_path: Path) -> tuple[str, ...]:
    """Return exact runtime requirements excluding the split editable packages."""

    requirements: list[str] = []
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        requirement = raw_line.split(" #", maxsplit=1)[0].strip()
        if not requirement or requirement.startswith("#"):
            continue
        if requirement.casefold().startswith(("ferrastra", "qpane", "cutecanvas")):
            continue
        requirements.append(requirement)
    return tuple(requirements)


def main(arguments: Sequence[str] | None = None) -> int:
    """Install the development overlay into the interpreter running this tool."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--canvas-root",
        type=Path,
        default=_DEFAULT_CANVAS_ROOT,
        help="Local canvas monorepo root (defaults to the sibling checkout).",
    )
    parsed = parser.parse_args(arguments)
    install_local_canvas_editables(
        python_executable=Path(sys.executable),
        canvas_root=parsed.canvas_root,
    )
    print("Installed and validated local editable Ferrastra, QPane, and CuteCanvas.")
    return 0


def _run_command(command: Sequence[str]) -> None:
    """Run one installation command and preserve a terminal failure."""

    subprocess.run(tuple(command), check=True)


def _validation_script(
    ferrastra_package: Path,
    qpane_package: Path,
    cutecanvas_package: Path,
) -> str:
    """Build a fresh-interpreter assertion for the editable import roots."""

    return (
        "from pathlib import Path; import cutecanvas, ferrastra, qpane; "
        f"ferrastra_root = Path({str(ferrastra_package.resolve())!r}); "
        f"qpane_root = Path({str(qpane_package.resolve())!r}); "
        f"cutecanvas_root = Path({str(cutecanvas_package.resolve())!r}); "
        "assert Path(ferrastra.__file__).resolve().is_relative_to("
        "ferrastra_root / 'src'); "
        "assert Path(qpane.__file__).resolve().is_relative_to(qpane_root / 'src'); "
        "assert Path(cutecanvas.__file__).resolve().is_relative_to("
        "cutecanvas_root / 'src')"
    )


if __name__ == "__main__":
    raise SystemExit(main())
