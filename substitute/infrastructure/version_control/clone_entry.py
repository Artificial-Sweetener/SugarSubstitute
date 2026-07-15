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

"""Perform one shallow pygit2 clone for the bounded parent process."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pygit2


def main(argv: list[str] | None = None) -> int:
    """Clone one public repository with automatic proxy detection."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    is_network_repository = args.repository_url.startswith(
        ("http://", "https://", "ssh://", "git://", "git@")
    )
    try:
        pygit2.clone_repository(
            args.repository_url,
            args.target_path,
            depth=1 if is_network_repository else 0,
            proxy=True if is_network_repository else None,
        )
    except (OSError, ValueError, pygit2.GitError) as error:
        print(str(error), file=sys.stderr, flush=True)
        return 1
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse the trusted parent process arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument("repository_url")
    parser.add_argument("target_path", type=Path)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
