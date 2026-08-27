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

"""Verify static ownership enforcement for input-asset semantics."""

from __future__ import annotations

from pathlib import Path

from tools.input_asset_governance.validation import validate_input_asset_governance


def test_rejects_transport_metadata_interpretation_outside_policy_owner(
    tmp_path: Path,
) -> None:
    """Competing image-upload metadata interpretation should fail governance."""

    source = tmp_path / "substitute" / "application" / "other.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def accepts(metadata: dict[str, object]) -> bool:\n"
        '    return metadata.get("image_upload") is True\n',
        encoding="utf-8",
    )

    diagnostics = validate_input_asset_governance(tmp_path)

    assert [(item.rule, item.path) for item in diagnostics] == [
        ("ASSET002", "substitute/application/other.py")
    ]


def test_rejects_class_name_transport_registry(tmp_path: Path) -> None:
    """A new load-image class inventory should fail static governance."""

    source = tmp_path / "substitute" / "transport.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        '_LOAD_IMAGE_CLASSES = frozenset({"LoadImage", "LoadImageMask"})\n',
        encoding="utf-8",
    )

    diagnostics = validate_input_asset_governance(tmp_path)

    assert [(item.rule, item.path) for item in diagnostics] == [
        ("ASSET003", "substitute/transport.py")
    ]


def test_requires_staging_to_enumerate_semantic_fields(tmp_path: Path) -> None:
    """The staging planner should not regress to endpoint or topology filtering."""

    source = (
        tmp_path
        / "substitute"
        / "application"
        / "generation"
        / "input_asset_staging_plan_service.py"
    )
    source.parent.mkdir(parents=True)
    source.write_text(
        "from somewhere import InputAssetFieldService\n",
        encoding="utf-8",
    )

    diagnostics = validate_input_asset_governance(tmp_path)

    assert [(item.rule, item.path) for item in diagnostics] == [
        (
            "ASSET006",
            "substitute/application/generation/input_asset_staging_plan_service.py",
        )
    ]
