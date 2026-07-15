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

"""Maintain canonical GPL license headers across first-party source files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Final, Sequence


PROJECT_START_YEAR: Final = 2026
PROJECT_TAGLINE: Final = "SugarSubstitute - The desktop native Qt front-end for ComfyUI"
COPYRIGHT_OWNER: Final = "Artificial Sweetener and contributors"
SUPPORTED_COMMENT_PREFIXES: Final = {
    ".py": "#",
    ".pyi": "#",
    ".spec": "#",
    ".cjs": "//",
    ".mjs": "//",
}
EXCLUDED_PATH_PREFIXES: Final = (
    ".local-release-channel/",
    ".venv/",
    "artifacts/",
    "build/",
    "dist/",
    "node_modules/",
    "third_party/",
)
ENCODING_DECLARATION = re.compile(r"^#.*?coding[:=][ \t]*[-\w.]+")
LICENSE_END_TEXT: Final = (
    "    along with this program.  If not, see <https://www.gnu.org/licenses/>."
)


class UnsupportedLicenseHeaderError(ValueError):
    """Report a GPL header that the policy cannot safely replace."""


@dataclass(frozen=True, slots=True)
class HeaderUpdate:
    """Describe one source file whose canonical header differs."""

    path: Path
    reason: str


def current_utc_year() -> int:
    """Return the current calendar year in UTC."""

    return datetime.now(UTC).year


def copyright_year_range(current_year: int) -> str:
    """Render the immutable project start through the current UTC year."""

    if current_year < PROJECT_START_YEAR:
        raise ValueError(
            f"Current year {current_year} predates SugarSubstitute's "
            f"{PROJECT_START_YEAR} start year."
        )
    if current_year == PROJECT_START_YEAR:
        return str(PROJECT_START_YEAR)
    return f"{PROJECT_START_YEAR}-{current_year}"


def render_header(comment_prefix: str, current_year: int) -> tuple[str, ...]:
    """Render the QPane-style GPL header for one comment syntax."""

    year_range = copyright_year_range(current_year)
    return (
        f"{comment_prefix}    {PROJECT_TAGLINE}",
        f"{comment_prefix}    Copyright (C) {year_range}  {COPYRIGHT_OWNER}",
        comment_prefix,
        f"{comment_prefix}    This program is free software: you can redistribute it and/or modify",
        f"{comment_prefix}    it under the terms of the GNU General Public License as published by",
        f"{comment_prefix}    the Free Software Foundation, either version 3 of the License, or",
        f"{comment_prefix}    (at your option) any later version.",
        comment_prefix,
        f"{comment_prefix}    This program is distributed in the hope that it will be useful,",
        f"{comment_prefix}    but WITHOUT ANY WARRANTY; without even the implied warranty of",
        f"{comment_prefix}    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the",
        f"{comment_prefix}    GNU General Public License for more details.",
        comment_prefix,
        f"{comment_prefix}    You should have received a copy of the GNU General Public License",
        f"{comment_prefix}{LICENSE_END_TEXT}",
    )


def rewrite_source(
    content: str,
    *,
    comment_prefix: str,
    current_year: int,
) -> str:
    """Return source text with exactly one current canonical header."""

    newline = _dominant_newline(content)
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()
    insertion_index = _header_insertion_index(lines, comment_prefix)
    body_start = insertion_index
    expected_start = f"{comment_prefix}    {PROJECT_TAGLINE}"

    if insertion_index < len(lines) and lines[insertion_index] == expected_start:
        body_start = _existing_header_end(lines, insertion_index, comment_prefix) + 1
    elif _has_unknown_gpl_header(lines, insertion_index, comment_prefix):
        raise UnsupportedLicenseHeaderError(
            "An unrecognized GPL header appears before the source body."
        )

    body = lines[body_start:]
    while body and not body[0].strip():
        body.pop(0)
    canonical_lines = (
        lines[:insertion_index]
        + list(render_header(comment_prefix, current_year))
        + [""]
        + body
    )
    return newline.join(canonical_lines) + newline


def tracked_source_files(repository_root: Path) -> tuple[Path, ...]:
    """Return tracked first-party source files governed by this policy."""

    patterns = tuple(f"*{suffix}" for suffix in SUPPORTED_COMMENT_PREFIXES)
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *patterns],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    relative_paths = (
        PurePosixPath(raw_path.decode("utf-8"))
        for raw_path in result.stdout.split(b"\0")
        if raw_path
    )
    included = (
        relative_path
        for relative_path in relative_paths
        if not _is_excluded(relative_path)
    )
    return tuple(
        repository_root.joinpath(*relative_path.parts)
        for relative_path in sorted(included, key=str)
    )


def inspect_headers(
    repository_root: Path,
    *,
    current_year: int,
    write: bool,
) -> tuple[HeaderUpdate, ...]:
    """Inspect or repair all governed files and return required updates."""

    updates: list[HeaderUpdate] = []
    replacements: list[tuple[Path, str]] = []
    has_conflicts = False
    for path in tracked_source_files(repository_root):
        with path.open("r", encoding="utf-8", newline="") as source_file:
            content = source_file.read()
        comment_prefix = SUPPORTED_COMMENT_PREFIXES[path.suffix.lower()]
        try:
            canonical = rewrite_source(
                content,
                comment_prefix=comment_prefix,
                current_year=current_year,
            )
        except UnsupportedLicenseHeaderError as exc:
            updates.append(HeaderUpdate(path=path, reason=str(exc)))
            has_conflicts = True
            continue
        if canonical == content:
            continue
        reason = (
            "missing header"
            if PROJECT_TAGLINE not in content[:2000]
            else "stale header"
        )
        updates.append(HeaderUpdate(path=path, reason=reason))
        replacements.append((path, canonical))
    if write and not has_conflicts:
        for path, canonical in replacements:
            with path.open("w", encoding="utf-8", newline="") as source_file:
                source_file.write(canonical)
    return tuple(updates)


def repository_root() -> Path:
    """Return the SugarSubstitute repository root."""

    return Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    """Check or repair repository license headers."""

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Report missing or stale headers without changing files.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Insert and update canonical headers in place.",
    )
    arguments = parser.parse_args(argv)
    write = bool(arguments.write)
    year = current_utc_year()
    updates = inspect_headers(
        repository_root(),
        current_year=year,
        write=write,
    )
    if not updates:
        print(f"License headers are current for {copyright_year_range(year)}.")
        return 0
    if write:
        conflicts = tuple(
            update
            for update in updates
            if update.reason not in {"missing header", "stale header"}
        )
        if conflicts:
            _print_updates(conflicts)
            return 1
        print(
            f"Updated {len(updates)} license headers for {copyright_year_range(year)}."
        )
        return 0
    print(
        f"{len(updates)} source files need license headers for "
        f"{copyright_year_range(year)}:"
    )
    _print_updates(updates)
    print("Run: .\\.venv\\Scripts\\python.exe tools\\license_headers.py --write")
    return 1


def _dominant_newline(content: str) -> str:
    """Return the existing newline convention, defaulting to repository LF."""

    return "\r\n" if content.count("\r\n") > content.count("\n") / 2 else "\n"


def _header_insertion_index(lines: list[str], comment_prefix: str) -> int:
    """Return the legal header position after a shebang and encoding line."""

    index = 0
    if lines and lines[0].startswith("#!"):
        index = 1
    if (
        comment_prefix == "#"
        and index < len(lines)
        and ENCODING_DECLARATION.match(lines[index])
    ):
        index += 1
    return index


def _existing_header_end(
    lines: list[str], start_index: int, comment_prefix: str
) -> int:
    """Return the final line of a recognized SugarSubstitute header."""

    expected_end = f"{comment_prefix}{LICENSE_END_TEXT}"
    for index in range(start_index, min(len(lines), start_index + 30)):
        if lines[index] == expected_end:
            return index
        if lines[index] and not lines[index].startswith(comment_prefix):
            break
    raise UnsupportedLicenseHeaderError(
        "The SugarSubstitute header is incomplete or malformed."
    )


def _has_unknown_gpl_header(
    lines: list[str], insertion_index: int, comment_prefix: str
) -> bool:
    """Detect a leading GPL comment block that this policy does not own."""

    if insertion_index >= len(lines) or not lines[insertion_index].startswith(
        comment_prefix
    ):
        return False
    comment_block: list[str] = []
    for line in lines[insertion_index : insertion_index + 40]:
        if line and not line.startswith(comment_prefix):
            break
        comment_block.append(line)
    return "GNU General Public License" in "\n".join(comment_block)


def _is_excluded(relative_path: PurePosixPath) -> bool:
    """Return whether a tracked path belongs outside first-party source."""

    path_text = relative_path.as_posix()
    return any(path_text.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES)


def _print_updates(updates: Sequence[HeaderUpdate]) -> None:
    """Print actionable paths and reasons for header updates."""

    root = repository_root()
    for update in updates:
        try:
            display_path = update.path.relative_to(root)
        except ValueError:
            display_path = update.path
        print(f"  {display_path}: {update.reason}")


if __name__ == "__main__":
    raise SystemExit(main())
