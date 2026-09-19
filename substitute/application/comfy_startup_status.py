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

"""Describe observed Comfy startup operations without treating logs as readiness."""

from __future__ import annotations

import re
from sugarsubstitute_shared.localization import ApplicationText, app_text

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def describe_comfy_startup_output(record: str) -> ApplicationText | None:
    """Translate recognized upstream markers; leave unknown output in diagnostics.

    These messages describe observed activity only. The readiness probe remains
    authoritative, including after Comfy prints its server URL.
    """
    line = _ANSI.sub("", record).strip()
    if line.startswith("[INFO] "):
        line = line[7:]
    if line.startswith(("Adding extra search path ", "Setting models directory to:")):
        return app_text("Configuring ComfyUI model folders.")
    if line.startswith("[START] Security scan"):
        return app_text("Checking ComfyUI extensions.")
    if line.startswith("[ComfyUI-Manager] Starting dependency installation"):
        return app_text("Preparing custom-node dependencies.")
    if line.startswith("Install: pip packages for "):
        return app_text(
            "Installing dependencies for %1.",
            _extension_name(line.removeprefix("Install: pip packages for ")),
        )
    for prefix in ("Install: install script for ", "## Execute management script for "):
        if line.startswith(prefix):
            return app_text(
                "Running setup for %1.", _extension_name(line[len(prefix) :])
            )
    if line.startswith(
        "[ComfyUI-Manager] Restarting to reapply dependency installation."
    ):
        return app_text("Restarting ComfyUI to apply updated dependencies.")
    if line.startswith(
        (
            "[DONE] Security scan",
            "Prestartup times for custom nodes:",
            "[ComfyUI-Manager] Startup script completed.",
            "Checkpoint files will always be loaded safely.",
        )
    ):
        return app_text("Loading the ComfyUI runtime.")
    if line.startswith(
        ("Total VRAM ", "pytorch version:", "Set vram state to:", "Device:")
    ):
        return app_text("Preparing ComfyUI's compute device.")
    if line.startswith("Using ") and "attention" in line.lower():
        return app_text("Configuring ComfyUI attention.")
    for prefix in (
        "### Loading:",
        "Trying to load custom node ",
        "Importing custom node ",
    ):
        if line.startswith(prefix):
            name = _extension_name(line[len(prefix) :])
            if name:
                return app_text("Loading custom node: %1.", name)
    if line.startswith("[Prompt Server] web root:"):
        return app_text("Loading ComfyUI custom nodes.")
    if line.startswith("Import times for custom nodes:"):
        return app_text("Finishing ComfyUI custom node loading.")
    imported = re.fullmatch(r"[0-9]+\.[0-9]+ seconds( \(IMPORT FAILED\))?: (.+)", line)
    if imported and "custom_nodes/" in imported[2].replace("\\", "/"):
        name = _extension_name(imported[2])
        if imported[1]:
            return app_text("Custom node %1 could not load.", name)
        return app_text("Loaded custom node: %1.", name)
    if line.startswith(
        ("Context impl SQLiteImpl.", "Running upgrade ", "Database upgraded from ")
    ):
        return app_text("Preparing the ComfyUI database.")
    if line.startswith("Background asset scan initiated"):
        return app_text("Scanning ComfyUI models and assets.")
    if line == "Starting server":
        return app_text("Starting the ComfyUI server.")
    if line.startswith("To see the GUI go to:"):
        return app_text("Connecting to ComfyUI.")
    fetched = re.fullmatch(r"FETCH ComfyRegistry Data: (\d+)/(\d+)", line)
    if fetched and 0 <= int(fetched[1]) <= int(fetched[2]) and int(fetched[2]) > 0:
        return app_text(
            "Updating the ComfyUI extension catalog (%1/%2).",
            int(fetched[1]),
            int(fetched[2]),
        )
    if line.startswith(
        ("FETCH ComfyRegistry Data", "[ComfyUI-Manager] default cache updated:")
    ):
        return app_text("Updating the ComfyUI extension catalog.")
    if line == "[ComfyUI-Manager] All startup tasks have been completed.":
        return app_text("ComfyUI extension setup is complete.")
    return None


def _extension_name(value: str) -> str:
    """Keep extension identity while omitting machine-specific parent directories."""
    return value.strip().strip("\"'").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
