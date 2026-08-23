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

"""Test Comfy import and prestartup timing parsing."""

from __future__ import annotations

from __future__ import annotations
from tools import startup_harness


def test_parse_comfy_import_times_reads_custom_node_block() -> None:
    """Comfy import timing output should become structured harness data."""

    output = """
Import times for custom nodes:
   0.2 seconds: E:\\ComfyUI\\custom_nodes\\sugarcubes
   1.4 seconds (IMPORT FAILED): E:\\ComfyUI\\custom_nodes\\broken

Other output
"""

    assert startup_harness.parse_comfy_import_times(output) == (
        {
            "seconds": 0.2,
            "status": "ok",
            "modulePath": r"E:\ComfyUI\custom_nodes\sugarcubes",
        },
        {
            "seconds": 1.4,
            "status": "failed",
            "modulePath": r"E:\ComfyUI\custom_nodes\broken",
        },
    )


def test_parse_comfy_import_times_ignores_comfy_ansi_info_prefix() -> None:
    """ANSI-colored Comfy log prefixes should not hide import timing records."""

    output = """
Import times for custom nodes:
\x1b[32m[INFO]\x1b[0m    0.1 seconds: E:\\ComfyUI\\custom_nodes\\SugarCubes
\x1b[32m[INFO]\x1b[0m    0.2 seconds (IMPORT FAILED): E:\\ComfyUI\\custom_nodes\\broken
"""

    assert startup_harness.parse_comfy_import_times(output) == (
        {
            "seconds": 0.1,
            "status": "ok",
            "modulePath": r"E:\ComfyUI\custom_nodes\SugarCubes",
        },
        {
            "seconds": 0.2,
            "status": "failed",
            "modulePath": r"E:\ComfyUI\custom_nodes\broken",
        },
    )


def test_parse_comfy_prestartup_times_reads_custom_node_block() -> None:
    """Comfy prestartup timing output should become structured harness data."""

    output = """
Prestartup times for custom nodes:
\x1b[32m[INFO]\x1b[0m    0.0 seconds: E:\\ComfyUI\\custom_nodes\\SubstituteManagedModelRoot
\x1b[32m[INFO]\x1b[0m    2.9 seconds: E:\\ComfyUI\\custom_nodes\\ComfyUI-Manager
\x1b[32m[INFO]\x1b[0m    0.4 seconds (PRESTARTUP FAILED): E:\\ComfyUI\\custom_nodes\\broken
"""

    assert startup_harness.parse_comfy_prestartup_times(output) == (
        {
            "seconds": 0.0,
            "status": "ok",
            "modulePath": r"E:\ComfyUI\custom_nodes\SubstituteManagedModelRoot",
        },
        {
            "seconds": 2.9,
            "status": "ok",
            "modulePath": r"E:\ComfyUI\custom_nodes\ComfyUI-Manager",
        },
        {
            "seconds": 0.4,
            "status": "failed",
            "modulePath": r"E:\ComfyUI\custom_nodes\broken",
        },
    )
