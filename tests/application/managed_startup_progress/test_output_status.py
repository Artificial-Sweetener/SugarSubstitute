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

"""Recognize observed Comfy startup markers without claiming readiness."""

import pytest
from substitute.application.comfy_startup_status import describe_comfy_startup_output
from sugarsubstitute_shared.presentation.localization import render_application_text


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        (
            "Adding extra search path checkpoints /models",
            "Configuring ComfyUI model folders.",
        ),
        (
            "[ComfyUI-Manager] Starting dependency installation/(de)activation for the extension",
            "Preparing custom-node dependencies.",
        ),
        (
            "Install: pip packages for '/comfy/custom_nodes/MyNode'",
            "Installing dependencies for MyNode.",
        ),
        (
            "Install: install script for '/comfy/custom_nodes/MyNode'",
            "Running setup for MyNode.",
        ),
        (
            "[ComfyUI-Manager] Restarting to reapply dependency installation.",
            "Restarting ComfyUI to apply updated dependencies.",
        ),
        ("Using pytorch attention", "Configuring ComfyUI attention."),
        (
            "Trying to load custom node /comfy/custom_nodes/MyNode",
            "Loading custom node: MyNode.",
        ),
        (
            r"0.5 seconds: C:\ComfyUI\custom_nodes\SugarCubes",
            "Loaded custom node: SugarCubes.",
        ),
        (
            "0.5 seconds (IMPORT FAILED): /comfy/custom_nodes/MyNode",
            "Custom node MyNode could not load.",
        ),
        ("Context impl SQLiteImpl.", "Preparing the ComfyUI database."),
        (
            "Background asset scan initiated for models, input, output",
            "Scanning ComfyUI models and assets.",
        ),
        (
            "[ComfyUI-Manager] All startup tasks have been completed.",
            "ComfyUI extension setup is complete.",
        ),
        ("[START] Security scan", "Checking ComfyUI extensions."),
        ("[DONE] Security scan", "Loading the ComfyUI runtime."),
        ("Prestartup times for custom nodes:", "Loading the ComfyUI runtime."),
        (
            "[INFO] Total VRAM 32768 MB, total RAM 65536 MB",
            "Preparing ComfyUI's compute device.",
        ),
        ("Device: cpu", "Preparing ComfyUI's compute device."),
        ("[Prompt Server] web root: package/web", "Loading ComfyUI custom nodes."),
        ("### Loading: ComfyUI-Manager", "Loading custom node: ComfyUI-Manager."),
        ("Import times for custom nodes:", "Finishing ComfyUI custom node loading."),
        ("\x1b[32m[INFO] Starting server\x1b[0m\n", "Starting the ComfyUI server."),
        ("To see the GUI go to: http://127.0.0.1:8188", "Connecting to ComfyUI."),
        (
            "FETCH ComfyRegistry Data: 10/100",
            "Updating the ComfyUI extension catalog (10/100).",
        ),
    ],
)
def test_known_output_describes_observed_work(record: str, expected: str) -> None:
    """Cover upstream markers, log prefixes and ANSI decoration with localized copy."""
    status = describe_comfy_startup_output(record)
    assert status is not None
    assert render_application_text(status) == expected


@pytest.mark.parametrize(
    "record",
    [
        "",
        "Unknown custom-node message",
        "Starting server failed",
        "Traceback: Device: unavailable",
    ],
)
def test_unknown_or_failed_output_does_not_invent_a_stage(record: str) -> None:
    """Keep unrecognized diagnostics available without interpreting them as progress."""
    assert describe_comfy_startup_output(record) is None
