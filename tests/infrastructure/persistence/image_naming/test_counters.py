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

"""Verify persistent image counter allocation."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.persistence.image_naming import (
    get_next_bucket_run_number,
    get_next_image_counter,
)


def test_get_next_image_counter_uses_matching_workflow_prefix(tmp_path: Path) -> None:
    """Return the highest matching workflow image index plus one."""

    (tmp_path / "001_my_flow_x.png").write_text("", encoding="utf-8")
    (tmp_path / "005_my_flow_y.png").write_text("", encoding="utf-8")
    (tmp_path / "003_other_flow.png").write_text("", encoding="utf-8")

    assert get_next_image_counter("My Flow", str(tmp_path)) == 6


def test_get_next_bucket_run_number_uses_all_image_prefixes(tmp_path: Path) -> None:
    """Return the highest valid image index plus one across one bucket."""

    (tmp_path / "001_my_flow_x.png").write_text("", encoding="utf-8")
    (tmp_path / "005_other_flow_y.png").write_text("", encoding="utf-8")
    (tmp_path / "not_a_run.png").write_text("", encoding="utf-8")

    assert get_next_bucket_run_number(str(tmp_path)) == 6
