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

"""Compare release versions shared by launcher update participants."""

from __future__ import annotations

import re


_PRERELEASE_IDENTIFIER = re.compile(r"^[0-9A-Za-z-]+$")


class _ReleaseVersion:
    """Represent the precedence-bearing parts of one release version."""

    def __init__(self, release: tuple[int, ...], prerelease: tuple[str, ...] | None):
        """Store validated release and prerelease components."""

        self.release = release
        self.prerelease = prerelease


def compare_release_versions(left: str, right: str) -> int:
    """Compare release versions using semantic prerelease precedence."""

    left_version = _parse_release_version(left)
    right_version = _parse_release_version(right)
    release_comparison = _compare_release_parts(
        left_version.release,
        right_version.release,
    )
    if release_comparison != 0:
        return release_comparison
    return _compare_prerelease_parts(
        left_version.prerelease,
        right_version.prerelease,
    )


def validate_release_version(version: str) -> None:
    """Reject values that are not safe semantic release identifiers."""

    _parse_release_version(version)


def is_prerelease_version(version: str) -> bool:
    """Return whether a validated release version has a prerelease suffix."""

    return _parse_release_version(version).prerelease is not None


def _parse_release_version(version: str) -> _ReleaseVersion:
    """Parse one release version without accepting path-like values."""

    normalized = version.removeprefix("v").strip()
    if not normalized:
        raise ValueError("Release version must not be empty.")
    if any(character in normalized for character in ("/", "\\", ":")):
        raise ValueError(f"Release version must be a plain tag value: {version}")
    release_text, separator, prerelease_text = normalized.partition("-")
    release_parts = release_text.split(".")
    if len(release_parts) < 2 or any(not part.isdigit() for part in release_parts):
        raise ValueError(f"Release version must be semantic: {version}")
    prerelease = None
    if separator:
        identifiers = tuple(prerelease_text.split("."))
        if not identifiers or any(
            not identifier or _PRERELEASE_IDENTIFIER.fullmatch(identifier) is None
            for identifier in identifiers
        ):
            raise ValueError(f"Release version must be semantic: {version}")
        prerelease = identifiers
    return _ReleaseVersion(tuple(int(part) for part in release_parts), prerelease)


def _compare_release_parts(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    """Compare numeric release components after zero-padding."""

    width = max(len(left), len(right))
    padded_left = (*left, *([0] * (width - len(left))))
    padded_right = (*right, *([0] * (width - len(right))))
    return (padded_left > padded_right) - (padded_left < padded_right)


def _compare_prerelease_parts(
    left: tuple[str, ...] | None,
    right: tuple[str, ...] | None,
) -> int:
    """Compare semantic prerelease identifiers."""

    if left is None or right is None:
        return (left is None) - (right is None)
    for left_identifier, right_identifier in zip(left, right, strict=False):
        if left_identifier == right_identifier:
            continue
        left_numeric = left_identifier.isdigit()
        right_numeric = right_identifier.isdigit()
        if left_numeric and right_numeric:
            return (int(left_identifier) > int(right_identifier)) - (
                int(left_identifier) < int(right_identifier)
            )
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return (left_identifier > right_identifier) - (
            left_identifier < right_identifier
        )
    return (len(left) > len(right)) - (len(left) < len(right))


__all__ = [
    "compare_release_versions",
    "is_prerelease_version",
    "validate_release_version",
]
