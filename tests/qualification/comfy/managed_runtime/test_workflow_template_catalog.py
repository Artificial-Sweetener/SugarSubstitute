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

"""Verify installed Comfy workflow-template catalog selection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.qualification.comfy.managed_runtime.workflow_template_catalog import (
    load_workflow_template_paths,
)


def test_catalog_selects_workflows_without_admitting_package_metadata(
    tmp_path: Path,
) -> None:
    """Index and search metadata JSON must not enter the workflow corpus."""

    (tmp_path / "first.json").write_text("{}", encoding="utf-8")
    (tmp_path / "second.json").write_text("{}", encoding="utf-8")
    (tmp_path / "fuse_options.json").write_text("{}", encoding="utf-8")
    (tmp_path / "index.schema.json").write_text("{}", encoding="utf-8")
    (tmp_path / "index.json").write_text(
        json.dumps(
            [
                {
                    "moduleName": "default",
                    "templates": [{"name": "second"}, {"name": "first"}],
                }
            ]
        ),
        encoding="utf-8",
    )

    assert load_workflow_template_paths(tmp_path) == (
        tmp_path / "first.json",
        tmp_path / "second.json",
    )


def test_catalog_rejects_missing_workflow_files(tmp_path: Path) -> None:
    """A catalog entry without its workflow must fail with its exact name."""

    (tmp_path / "index.json").write_text(
        json.dumps([{"templates": [{"name": "missing"}]}]),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="missing.json"):
        load_workflow_template_paths(tmp_path)
