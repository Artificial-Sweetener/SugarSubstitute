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

"""Build bounded metadata tooltips for live cube stack items."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from html import escape
import re
from typing import Any

from sugarsubstitute_shared.localization import opaque_text

_MAX_DESCRIPTION_LENGTH = 220
_MAX_LIST_VALUES = 3
_TOOLTIP_WIDTH_PX = 420
_TOOLTIP_STYLE = (
    f"max-width: {_TOOLTIP_WIDTH_PX}px; "
    f"width: {_TOOLTIP_WIDTH_PX}px; "
    "white-space: normal; "
    "word-wrap: break-word; "
    "overflow-wrap: anywhere;"
)


@dataclass(frozen=True)
class CubeStackTooltipMetadata:
    """Store normalized cube metadata intended for stack tooltip display."""

    default_alias: str
    version: str
    source_pack: str
    author: str
    supported_models: tuple[str, ...]
    description: str
    tags: tuple[str, ...]

    @property
    def source_line(self) -> str:
        """Return the readable source line for pack and author metadata."""

        if self.source_pack and self.author:
            return f"{self.source_pack} by {self.author}"
        return self.source_pack


def cube_stack_tooltip_metadata_from_state(
    *,
    alias: str,
    cube_state: object,
) -> CubeStackTooltipMetadata:
    """Extract tooltip metadata from one loaded workflow cube state."""

    ui_payload = _mapping_from_value(getattr(cube_state, "ui", None))
    canonical_cube = _mapping_from_value(ui_payload.get("canonical_cube"))
    canonical_metadata = _mapping_from_value(canonical_cube.get("metadata"))
    source = _mapping_from_value(ui_payload.get("source"))
    source_pack, author = _source_pack_and_author(
        source=source,
        cube_id=_first_text(
            canonical_cube.get("cube_id"),
            getattr(cube_state, "cube_id", ""),
        ),
    )

    return CubeStackTooltipMetadata(
        default_alias=_first_text(
            canonical_metadata.get("default_alias"),
            getattr(cube_state, "display_name", ""),
            alias,
        ),
        version=_format_version(
            _first_text(
                canonical_cube.get("version"), getattr(cube_state, "version", "")
            )
        ),
        source_pack=source_pack,
        author=author,
        supported_models=_normalized_text_sequence(
            canonical_metadata.get("supported_models")
        ),
        description=_bounded_description(
            _first_text(
                canonical_cube.get("description"),
                canonical_metadata.get("description"),
            )
        ),
        tags=_normalized_text_sequence(canonical_metadata.get("tags")),
    )


def build_cube_stack_tooltip_text(
    metadata: CubeStackTooltipMetadata,
    *,
    rich_text: bool = True,
) -> str:
    """Return a bounded tooltip string for one cube stack item."""

    lines = _plain_tooltip_lines(metadata)
    if not rich_text:
        return "\n".join(lines)

    rich_lines = _rich_tooltip_lines(metadata)
    return opaque_text(
        f'<div style="{_TOOLTIP_STYLE}">' + "<br>".join(rich_lines) + "</div>"
    )


def build_cube_stack_tooltip_for_state(
    *,
    alias: str,
    cube_state: object,
    rich_text: bool = True,
) -> str:
    """Build tooltip text directly from one loaded workflow cube state."""

    return build_cube_stack_tooltip_text(
        cube_stack_tooltip_metadata_from_state(alias=alias, cube_state=cube_state),
        rich_text=rich_text,
    )


def _plain_tooltip_lines(metadata: CubeStackTooltipMetadata) -> list[str]:
    """Return plain-text tooltip lines in product-requested order."""

    lines = [_headline(metadata)]
    if metadata.source_line:
        lines.append(metadata.source_line)

    detail_lines = _detail_lines(metadata)
    if detail_lines:
        lines.append("")
        lines.extend(detail_lines)
    return [line for line in lines if line or detail_lines]


def _rich_tooltip_lines(metadata: CubeStackTooltipMetadata) -> list[str]:
    """Return rich-text tooltip lines in product-requested order."""

    lines = [_rich_headline(metadata)]
    if metadata.source_line:
        lines.append(escape(metadata.source_line))

    detail_lines = _rich_detail_lines(metadata)
    if detail_lines:
        lines.append("")
        lines.extend(detail_lines)
    return lines


def _headline(metadata: CubeStackTooltipMetadata) -> str:
    """Return first-line alias and version text."""

    if metadata.version:
        return f"{metadata.default_alias}, {metadata.version}"
    return metadata.default_alias


def _rich_headline(metadata: CubeStackTooltipMetadata) -> str:
    """Return escaped first-line alias and version text."""

    alias = f"<b>{escape(metadata.default_alias)}</b>"
    if metadata.version:
        return f"{alias}, {escape(metadata.version)}"
    return alias


def _detail_lines(metadata: CubeStackTooltipMetadata) -> list[str]:
    """Return optional plain-text metadata detail lines."""

    lines: list[str] = []
    models = _compact_values(metadata.supported_models)
    if models:
        lines.append(f"Supported models: {models}")
    if metadata.description:
        lines.append(f"Description: {metadata.description}")
    tags = _compact_values(metadata.tags)
    if tags:
        lines.append(f"Tags: {tags}")
    return lines


def _rich_detail_lines(metadata: CubeStackTooltipMetadata) -> list[str]:
    """Return optional rich-text metadata detail lines."""

    lines: list[str] = []
    models = _compact_values(metadata.supported_models)
    if models:
        lines.append(f"<b>Supported models:</b> {escape(models)}")
    if metadata.description:
        lines.append(f"<b>Description:</b> {escape(metadata.description)}")
    tags = _compact_values(metadata.tags)
    if tags:
        lines.append(f"<b>Tags:</b> {escape(tags)}")
    return lines


def _mapping_from_value(value: object) -> Mapping[str, Any]:
    """Return a string-keyed mapping view for untyped payloads."""

    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _first_text(*values: object) -> str:
    """Return the first non-empty string value after whitespace normalization."""

    for value in values:
        if isinstance(value, str):
            normalized = _normalize_inline_text(value)
            if normalized:
                return normalized
    return ""


def _format_version(version: str) -> str:
    """Return display-ready cube version text."""

    stripped = version.strip()
    if not stripped:
        return ""
    if stripped.lower().startswith("v"):
        return stripped
    return f"v{stripped}"


def _source_pack_and_author(
    *,
    source: Mapping[str, Any],
    cube_id: str,
) -> tuple[str, str]:
    """Return readable pack and author metadata from source payloads."""

    owner = _first_text(source.get("owner"))
    repo = _first_text(source.get("repo"))
    if owner or repo:
        return repo, owner

    for value in (
        source.get("repo_ref"),
        cube_id,
        source.get("path"),
    ):
        pack_author = _pack_author_from_path_like(_first_text(value))
        if pack_author != ("", ""):
            return pack_author
    return "", ""


def _pack_author_from_path_like(value: str) -> tuple[str, str]:
    """Parse author and pack from one repository-like path."""

    if not value:
        return "", ""
    normalized = value.replace("\\", "/")
    parts = [part.strip() for part in normalized.split("/") if part.strip()]
    if len(parts) < 2:
        return "", ""

    if "github.com" in [part.lower() for part in parts]:
        github_index = [part.lower() for part in parts].index("github.com")
        candidate = parts[github_index + 1 : github_index + 3]
        if len(candidate) == 2:
            return candidate[1], candidate[0]

    return parts[1], parts[0]


def _normalized_text_sequence(value: object) -> tuple[str, ...]:
    """Return normalized unique text values from untrusted sequence payloads."""

    if isinstance(value, str) or not isinstance(value, Iterable):
        return ()

    normalized_values: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = _normalize_inline_text(item)
        if not normalized:
            continue
        lookup = normalized.casefold()
        if lookup in seen:
            continue
        seen.add(lookup)
        normalized_values.append(normalized)
    return tuple(normalized_values)


def _compact_values(values: Sequence[str]) -> str:
    """Return display text for a bounded list with an overflow count."""

    if not values:
        return ""
    visible = values[:_MAX_LIST_VALUES]
    overflow = len(values) - len(visible)
    result = ", ".join(visible)
    if overflow > 0:
        result = f"{result} +{overflow}"
    return result


def _bounded_description(value: str) -> str:
    """Return a normalized description capped for tooltip readability."""

    normalized = _normalize_inline_text(value)
    if len(normalized) <= _MAX_DESCRIPTION_LENGTH:
        return normalized
    return normalized[:_MAX_DESCRIPTION_LENGTH].rstrip() + "..."


def _normalize_inline_text(value: str) -> str:
    """Collapse internal whitespace for one tooltip field."""

    return re.sub(r"\s+", " ", value).strip()


__all__ = [
    "CubeStackTooltipMetadata",
    "build_cube_stack_tooltip_for_state",
    "build_cube_stack_tooltip_text",
    "cube_stack_tooltip_metadata_from_state",
]
