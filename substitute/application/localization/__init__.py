#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Expose application localization services."""

from substitute.application.localization.node_presentation_service import (
    ApplicationTextRenderer,
    NodePresentationService,
    NodeTextCatalogResolver,
    NodeTextCatalogSnapshotProvider,
)
from substitute.application.localization.comfy_node_catalog_store import (
    ActiveComfyNodeCatalogStore,
    ComfyNodeCatalogSelection,
)

__all__ = [
    "ActiveComfyNodeCatalogStore",
    "ApplicationTextRenderer",
    "ComfyNodeCatalogSelection",
    "NodePresentationService",
    "NodeTextCatalogResolver",
    "NodeTextCatalogSnapshotProvider",
]
