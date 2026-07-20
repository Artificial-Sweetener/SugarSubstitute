#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Expose locale-neutral localization domain values."""

from substitute.domain.localization.node_text import (
    FieldPresentation,
    NodeCatalogText,
    NodeFieldCatalogText,
    NodeFieldPresentationRequest,
    NodePresentation,
    NodePresentationRequest,
    NodeTextCatalog,
    NodeTextCatalogSnapshot,
    NodeTextSource,
    ResolvedCatalogText,
    ResolvedFieldCatalogText,
    ResolvedNodeCatalogText,
)

__all__ = [
    "FieldPresentation",
    "NodeCatalogText",
    "NodeFieldCatalogText",
    "NodeFieldPresentationRequest",
    "NodePresentation",
    "NodePresentationRequest",
    "NodeTextCatalog",
    "NodeTextCatalogSnapshot",
    "NodeTextSource",
    "ResolvedCatalogText",
    "ResolvedFieldCatalogText",
    "ResolvedNodeCatalogText",
]
