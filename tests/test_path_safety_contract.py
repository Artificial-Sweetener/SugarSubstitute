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

"""Contract tests for shared fail-closed path safety helpers."""

from __future__ import annotations

from pathlib import Path

from substitute.shared.util.path_safety import (
    ensure_within_root,
    safe_component,
    validate_archive_member_path,
    validate_top_level_name,
)
import pytest


def test_validate_top_level_name_trims_and_accepts_single_segment() -> None:
    """Top-level name validation should trim whitespace and keep one segment."""

    assert validate_top_level_name("  Workflow A  ", subject="Workflow") == "Workflow A"


def test_validate_top_level_name_rejects_invalid_values() -> None:
    """Top-level name validation should reject empty, nested, and absolute values."""

    for value in (
        "",
        ".",
        "..",
        " . ",
        " .. ",
        "../escape",
        "nested/name",
        "nested\\name",
        "C:/abs",
        "name\u0000bad",
    ):
        with pytest.raises(ValueError):
            validate_top_level_name(value, subject="Workflow")


def test_ensure_within_root_returns_resolved_path(tmp_path: Path) -> None:
    """Path validator should resolve and return candidate path under root."""

    root = tmp_path / "root"
    root.mkdir()
    candidate = root / "child" / "file.txt"
    candidate.parent.mkdir(parents=True)
    candidate.write_text("x", encoding="utf-8")

    resolved = ensure_within_root(candidate, root_path=root, subject="Artifact")

    assert resolved == candidate.resolve()


def test_ensure_within_root_rejects_escape_attempt(tmp_path: Path) -> None:
    """Path validator should reject candidates that resolve outside the root."""

    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match="outside allowed root"):
        ensure_within_root(outside, root_path=root, subject="Artifact")


def test_ensure_within_root_rejects_non_top_level_when_required(tmp_path: Path) -> None:
    """Top-level enforcement should reject nested paths below root."""

    root = tmp_path / "root"
    root.mkdir()
    nested = root / "a" / "b.txt"
    nested.parent.mkdir(parents=True)
    nested.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match="top-level child"):
        ensure_within_root(
            nested,
            root_path=root,
            subject="Artifact",
            require_top_level=True,
        )


def test_safe_component_matches_legacy_sanitization_contract() -> None:
    """Filename sanitizer should preserve legacy replacement behavior."""

    assert safe_component("A/B:C\\D\0 ") == "A_B_C_D_"
    assert safe_component(" clean ") == "clean"


def test_validate_archive_member_path_accepts_relative_member() -> None:
    """Archive member validation should keep valid normalized relative members."""

    assert (
        validate_archive_member_path("folder/item.cube", subject="Cube graph")
        == "folder/item.cube"
    )


def test_validate_archive_member_path_rejects_invalid_members() -> None:
    """Archive member validation should reject empty, absolute, and traversal paths."""

    invalid_names = (
        "",
        "/abs/path.cube",
        "\\absolute\\path.cube",
        "../escape.cube",
        "..\\escape.cube",
        "folder/../../escape.cube",
        "folder\\..\\escape.cube",
        "C:/drive/path.cube",
    )
    for member_name in invalid_names:
        with pytest.raises(ValueError):
            validate_archive_member_path(member_name, subject="Cube graph")
