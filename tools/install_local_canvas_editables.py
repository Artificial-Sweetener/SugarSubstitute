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

"""Install and validate the paired local QPane and CuteCanvas development overlay."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_QPANE_ROOT = _REPOSITORY_ROOT.parent / "qpane"

CommandRunner = Callable[[Sequence[str]], None]


def install_local_canvas_editables(
    *,
    python_executable: Path,
    qpane_root: Path,
    runner: CommandRunner | None = None,
) -> None:
    """Install the paired editable packages and verify their resolved source roots.

    Args:
        python_executable: Interpreter of the target virtual environment.
        qpane_root: Local QPane monorepo root containing both package roots.
        runner: Subprocess boundary used for deterministic automation tests.

    Raises:
        FileNotFoundError: If the paired local package roots are unavailable.
        subprocess.CalledProcessError: If installation or validation fails.
    """

    qpane_package, cutecanvas_package = local_canvas_package_roots(qpane_root)
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
    execute(
        (
            python,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--editable",
            str(qpane_package),
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
            _validation_script(qpane_package, cutecanvas_package),
        )
    )


def local_canvas_package_roots(qpane_root: Path) -> tuple[Path, Path]:
    """Return validated paired local package roots for one QPane checkout."""

    root = Path(qpane_root).resolve()
    qpane_package = root / "packages" / "qpane"
    cutecanvas_package = root / "packages" / "cutecanvas"
    for package in (qpane_package, cutecanvas_package):
        if not (package / "pyproject.toml").is_file():
            raise FileNotFoundError(f"Local canvas package is unavailable: {package}")
    return qpane_package, cutecanvas_package


def _non_canvas_runtime_requirements(requirements_path: Path) -> tuple[str, ...]:
    """Return exact runtime requirements excluding the split editable packages."""

    requirements: list[str] = []
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        requirement = raw_line.split(" #", maxsplit=1)[0].strip()
        if not requirement or requirement.startswith("#"):
            continue
        if requirement.casefold().startswith(("qpane", "cutecanvas")):
            continue
        requirements.append(requirement)
    return tuple(requirements)


def main(arguments: Sequence[str] | None = None) -> int:
    """Install the development overlay into the interpreter running this tool."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--qpane-root",
        type=Path,
        default=_DEFAULT_QPANE_ROOT,
        help="Local QPane monorepo root (defaults to the sibling checkout).",
    )
    parsed = parser.parse_args(arguments)
    install_local_canvas_editables(
        python_executable=Path(sys.executable),
        qpane_root=parsed.qpane_root,
    )
    print("Installed and validated local editable QPane and CuteCanvas packages.")
    return 0


def _run_command(command: Sequence[str]) -> None:
    """Run one installation command and preserve a terminal failure."""

    subprocess.run(tuple(command), check=True)


def _validation_script(qpane_package: Path, cutecanvas_package: Path) -> str:
    """Build a fresh-interpreter assertion for the paired editable import roots."""

    return (
        "from pathlib import Path; import cutecanvas, qpane; "
        f"qpane_root = Path({str(qpane_package.resolve())!r}); "
        f"cutecanvas_root = Path({str(cutecanvas_package.resolve())!r}); "
        "assert Path(qpane.__file__).resolve().is_relative_to(qpane_root / 'src'); "
        "assert Path(cutecanvas.__file__).resolve().is_relative_to("
        "cutecanvas_root / 'src')"
    )


if __name__ == "__main__":
    raise SystemExit(main())
