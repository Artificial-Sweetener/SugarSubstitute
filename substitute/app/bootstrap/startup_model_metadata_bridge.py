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

"""Adapt the shell model-metadata update bridge for startup wiring."""

from __future__ import annotations

from typing import Any, cast

from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
)
from substitute.presentation.shell.model_metadata_update_bridge import (
    ModelMetadataUpdateBridge,
)


def create_model_metadata_update_bridge(
    parent: object,
) -> ModelMetadataUpdateSignalBridgeProtocol:
    """Create the Qt-backed model metadata update bridge for one shell frame."""

    return cast(
        ModelMetadataUpdateSignalBridgeProtocol,
        ModelMetadataUpdateBridge(cast(Any, parent)),
    )


__all__ = ["create_model_metadata_update_bridge"]
