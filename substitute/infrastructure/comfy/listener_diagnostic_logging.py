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

"""Emit structured diagnostics selected by Comfy listener collaborators."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventDiagnostic,
)
from substitute.infrastructure.comfy.cube_output_event_router import (
    CubeOutputDiagnostic,
)
from substitute.infrastructure.comfy.model_load_source_metadata_resolver import (
    ModelLoadSourceMetadataDiagnostic,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceDiagnostic,
)
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventRejectionDiagnostic,
)
from substitute.shared.logging.logger import log_debug, log_info, log_warning


@dataclass(frozen=True)
class ListenerDiagnosticLogger:
    """Emit listener collaborator diagnostics through one logger."""

    logger: logging.Logger

    def binary_event(self, diagnostic: BinaryEventDiagnostic) -> None:
        """Emit one binary event diagnostic at its selected level."""

        _log_binary_event_diagnostic(self.logger, diagnostic)

    def model_load_source_metadata(
        self,
        diagnostic: ModelLoadSourceMetadataDiagnostic,
    ) -> None:
        """Emit one model-load source metadata diagnostic."""

        _log_model_load_source_metadata_diagnostic(self.logger, diagnostic)

    def cube_output(self, diagnostic: CubeOutputDiagnostic) -> None:
        """Emit one cube-output diagnostic at its selected level."""

        _log_cube_output_diagnostic(self.logger, diagnostic)

    def visual_event(self, diagnostic: VisualEventRejectionDiagnostic) -> None:
        """Emit one visual event diagnostic at its selected level."""

        _log_visual_event_diagnostic(self.logger, diagnostic)

    def output_source(self, diagnostic: OutputSourceDiagnostic) -> None:
        """Emit one output-source diagnostic at its selected level."""

        _log_output_source_diagnostic(self.logger, diagnostic)


def _log_binary_event_diagnostic(
    logger: logging.Logger,
    diagnostic: BinaryEventDiagnostic,
) -> None:
    """Emit one binary event diagnostic at its selected level."""

    if diagnostic.level == "warning":
        log_warning(logger, diagnostic.message, **diagnostic.fields)
        return
    if diagnostic.level == "debug":
        log_debug(logger, diagnostic.message, **diagnostic.fields)
        return
    log_info(logger, diagnostic.message, **diagnostic.fields)


def _log_model_load_source_metadata_diagnostic(
    logger: logging.Logger,
    diagnostic: ModelLoadSourceMetadataDiagnostic,
) -> None:
    """Emit one model-load source metadata diagnostic."""

    log_info(logger, diagnostic.message, **diagnostic.fields)


def _log_cube_output_diagnostic(
    logger: logging.Logger,
    diagnostic: CubeOutputDiagnostic,
) -> None:
    """Emit one cube-output diagnostic at its selected level."""

    if diagnostic.level == "debug":
        log_debug(logger, diagnostic.message, **diagnostic.fields)
        return
    if diagnostic.level == "info":
        log_info(logger, diagnostic.message, **diagnostic.fields)
        return
    log_warning(logger, diagnostic.message, **diagnostic.fields)


def _log_visual_event_diagnostic(
    logger: logging.Logger,
    diagnostic: VisualEventRejectionDiagnostic,
) -> None:
    """Emit one visual event diagnostic at its selected level."""

    if diagnostic.level == "debug":
        log_debug(logger, diagnostic.message, **diagnostic.fields)
        return
    log_warning(logger, diagnostic.message, **diagnostic.fields)


def _log_output_source_diagnostic(
    logger: logging.Logger,
    diagnostic: OutputSourceDiagnostic,
) -> None:
    """Emit one output-source diagnostic at its selected level."""

    if diagnostic.level == "debug":
        log_debug(logger, diagnostic.message, **diagnostic.fields)
        return
    log_warning(logger, diagnostic.message, **diagnostic.fields)


__all__ = [
    "ListenerDiagnosticLogger",
]
