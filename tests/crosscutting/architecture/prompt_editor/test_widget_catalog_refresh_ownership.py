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

"""Enforce focused ownership of prompt-editor catalog refresh effects."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_catalog_refresh_facade_owns_cross_consumer_thumbnail_invalidation() -> None:
    """Keep catalog cache and repaint sequencing out of the QFluent adapter."""

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    facade_source = (PROMPT_PRESENTATION_ROOT / "catalog_refresh_facade.py").read_text(
        encoding="utf-8"
    )

    for ownership_marker in (
        "bindings.clear_thumbnail_cache()",
        'bindings.refresh_thumbnail_paint("lora_thumbnail_cache_clear")',
        "bindings.update_host()",
    ):
        assert ownership_marker in facade_source
        assert ownership_marker not in widget_source

    assert "PromptLoraMetadataRefreshHost" not in (
        PROMPT_PRESENTATION_ROOT / "features" / "lora_metadata_refresh_lifecycle.py"
    ).read_text(encoding="utf-8")
