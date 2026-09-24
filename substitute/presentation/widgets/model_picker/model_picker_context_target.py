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

"""Adapt rich model choices to shared metadata context-menu targets."""

from __future__ import annotations

from substitute.application.model_metadata import RichChoiceItem
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
)


def model_picker_context_target(
    item: RichChoiceItem | None,
) -> ModelMetadataContextMenuTarget | None:
    """Return the metadata action target retained by one rich model choice."""

    if item is None:
        return None
    catalog_item = item.catalog_item
    return ModelMetadataContextMenuTarget(
        title=item.title,
        subtitle=item.subtitle,
        backend_value=item.value,
        relative_path=(
            item.value if catalog_item is None else catalog_item.relative_path
        ),
        model_kind=item.model_kind,
        model_page_url=(None if catalog_item is None else catalog_item.model_page_url),
        provider_links=(() if catalog_item is None else catalog_item.provider_links),
        sha256=(None if catalog_item is None else catalog_item.sha256),
    )


__all__ = ["model_picker_context_target"]
