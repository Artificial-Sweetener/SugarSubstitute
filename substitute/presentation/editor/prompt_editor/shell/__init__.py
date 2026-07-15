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

"""Expose prompt-editor shell chrome owners."""

from __future__ import annotations

from .fill_plane import (
    PromptFillPlane,
    PromptFillPlaneHost,
    PromptFillPlaneSurface,
    PromptResizeHandle,
    PromptResizeHandleHost,
    update_prompt_fill_backing,
)
from .qfluent_chrome import (
    PromptShellChromeHost,
    PromptShellChromeSurface,
    PromptShellQFluentChrome,
)
from .context_menu_controller import (
    PromptShellContextInsertState,
    PromptShellContextMenuController,
    PromptShellContextMenuOpening,
    PromptShellDiagnosticAction,
    PromptShellPromptMenuRequest,
    PromptShellPromptMenuRequestProvider,
    PromptShellSelectionSnapshot,
    PromptShellSegmentPresetMenuModel,
)
from .sizing_controller import (
    PromptShellSizingController,
    PromptShellSizingDocument,
    PromptShellSizingHost,
    PromptShellSizingSignal,
)
from .scroll_delegate import (
    PromptShellScrollDelegate,
    PromptShellScrollHost,
    PromptShellScrollSurface,
    PromptShellSignal,
)
from .widget import (
    PROMPT_EDITOR_HOST_FACADE_INVENTORY,
    PROMPT_EDITOR_PUBLIC_WIDGET_SIGNALS,
    PROMPT_EDITOR_PUBLIC_WIDGET_BOUNDARY,
    PromptEditorHostFacadeInventory,
    PromptEditorPublicWidgetBoundary,
    PromptEditorShell,
)

__all__ = [
    "PROMPT_EDITOR_HOST_FACADE_INVENTORY",
    "PROMPT_EDITOR_PUBLIC_WIDGET_BOUNDARY",
    "PROMPT_EDITOR_PUBLIC_WIDGET_SIGNALS",
    "PromptFillPlane",
    "PromptFillPlaneHost",
    "PromptFillPlaneSurface",
    "PromptEditorHostFacadeInventory",
    "PromptEditorPublicWidgetBoundary",
    "PromptEditorShell",
    "PromptResizeHandle",
    "PromptResizeHandleHost",
    "PromptShellChromeHost",
    "PromptShellChromeSurface",
    "PromptShellContextInsertState",
    "PromptShellContextMenuController",
    "PromptShellContextMenuOpening",
    "PromptShellDiagnosticAction",
    "PromptShellPromptMenuRequest",
    "PromptShellPromptMenuRequestProvider",
    "PromptShellSelectionSnapshot",
    "PromptShellSegmentPresetMenuModel",
    "PromptShellQFluentChrome",
    "PromptShellScrollDelegate",
    "PromptShellScrollHost",
    "PromptShellScrollSurface",
    "PromptShellSignal",
    "PromptShellSizingController",
    "PromptShellSizingDocument",
    "PromptShellSizingHost",
    "PromptShellSizingSignal",
    "update_prompt_fill_backing",
]
