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

"""Provide fail-closed path and name validation helpers for IO boundaries."""

from __future__ import annotations

from pathlib import Path, PurePosixPath


def validate_top_level_name(name: str, *, subject: str) -> str:
    """Validate a top-level name and reject traversal or platform path semantics.

    Args:
        name: Candidate direct name supplied by UI/user state.
        subject: Human-readable entity label for error messages.

    Returns:
        Normalized, stripped name.

    Raises:
        ValueError: If name is empty, nested, absolute, traversal-like, or unsafe.
    """

    normalized = name.strip()
    if not normalized:
        raise ValueError(f"{subject} name must be a non-empty string.")
    if "\u0000" in normalized:
        raise ValueError(
            f"{subject} name '{name}' is invalid; null bytes are forbidden."
        )
    if normalized in {".", ".."}:
        raise ValueError(
            f"{subject} name '{name}' is invalid; traversal tokens are forbidden."
        )
    if "/" in normalized or "\\" in normalized:
        raise ValueError(
            f"{subject} name '{name}' is invalid; only top-level names are allowed."
        )
    if ":" in normalized:
        raise ValueError(
            f"{subject} name '{name}' is invalid; drive-qualified names are forbidden."
        )

    candidate = Path(normalized)
    if candidate.is_absolute() or len(candidate.parts) != 1:
        raise ValueError(
            f"{subject} name '{name}' is invalid; only top-level names are allowed."
        )

    return normalized


def safe_component(name: str) -> str:
    """Return conservative filename-safe component text.

    This helper mirrors legacy behavior used by output-image naming paths.
    """

    return (
        name.replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("\u0000", "_")
        .strip()
    )


def validate_archive_member_path(member_name: str, *, subject: str) -> str:
    """Validate archive member path and fail closed for traversal semantics.

    Args:
        member_name: Raw member path inside an archive payload.
        subject: Human-readable label for diagnostics.

    Returns:
        Normalized member path.

    Raises:
        ValueError: If member path is empty, absolute, contains `..`, or is unsafe.
    """

    normalized = member_name.strip()
    if not normalized:
        raise ValueError(f"{subject} archive member path is empty.")
    if "\\" in normalized:
        raise ValueError(f"{subject} archive member path is invalid: {member_name}")

    pure_path = PurePosixPath(normalized)
    if pure_path.is_absolute():
        raise ValueError(f"{subject} archive member path is invalid: {member_name}")
    if ".." in pure_path.parts or "." in pure_path.parts:
        raise ValueError(f"{subject} archive member path is invalid: {member_name}")
    if any(":" in part for part in pure_path.parts):
        raise ValueError(f"{subject} archive member path is invalid: {member_name}")

    return normalized


def ensure_within_root(
    candidate_path: Path,
    *,
    root_path: Path,
    subject: str,
    require_top_level: bool = False,
) -> Path:
    """Validate candidate_path resolves inside root_path.

    Args:
        candidate_path: Path to validate.
        root_path: Root path candidate_path must be contained within.
        subject: Human-readable entity label for diagnostics.
        require_top_level: Whether candidate_path must be a direct child of root_path.

    Returns:
        Resolved candidate path.

    Raises:
        ValueError: If path escapes root_path or violates top-level constraint.
    """

    resolved_candidate = candidate_path.resolve()
    resolved_root = root_path.resolve()
    try:
        relative = resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(
            f"{subject} path resolves outside allowed root '{resolved_root}': {resolved_candidate}"
        ) from exc

    if require_top_level and len(relative.parts) != 1:
        raise ValueError(
            f"{subject} path must be a top-level child of '{resolved_root}', got '{resolved_candidate}'."
        )

    return resolved_candidate


__all__ = [
    "safe_component",
    "validate_archive_member_path",
    "ensure_within_root",
    "validate_top_level_name",
]
