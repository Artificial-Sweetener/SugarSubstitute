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

"""Verify explicit policy for live bundled-workflow probes."""

from __future__ import annotations

from tests.qualification.comfy.bundled_workflows.rendering_runner import (
    bundled_workflow_probe_deferment,
)


def test_ideogram_bounding_box_probe_has_an_exact_deferment() -> None:
    """Keep the unsupported live probe skipped without suppressing other workflows."""

    reason = bundled_workflow_probe_deferment("api_ideogram_p_image_t2i")

    assert reason is not None
    assert "existing Input Canvas owner" in reason
    assert bundled_workflow_probe_deferment("default") is None
