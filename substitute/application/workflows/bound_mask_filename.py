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

"""Build bounded deterministic filenames for editable mask artifacts."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from substitute.shared.util.path_safety import validate_top_level_name

MAX_BOUND_MASK_FILENAME_LENGTH = 224
_SOURCE_LABEL_LIMIT = 80
_GRAPH_IDENTITY_LIMIT = 48
_NODE_NAME_LIMIT = 40
_UNSAFE_FILENAME_COMPONENT_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_FILENAME_SEPARATOR_RE = re.compile(r"_+")


def bound_mask_filename(
    *,
    associated_image_path: Path,
    cube_alias: str,
    mask_node_name: str,
    image_size: tuple[int, int] | None,
) -> str:
    """Return a readable mask filename with deterministic collision identity."""

    filename = "__".join(
        (
            _bounded_component(
                _safe_filename_component(associated_image_path.stem),
                limit=_SOURCE_LABEL_LIMIT,
            ),
            _short_path_hash(associated_image_path),
            _image_size_component(image_size),
            _bounded_component(
                _safe_identity_component(cube_alias),
                limit=_GRAPH_IDENTITY_LIMIT,
            ),
            _bounded_component(
                _safe_filename_component(mask_node_name),
                limit=_NODE_NAME_LIMIT,
            ),
        )
    )
    result = f"{filename}.png"
    if len(result) > MAX_BOUND_MASK_FILENAME_LENGTH:
        raise ValueError("Bound mask filename components exceed the safe limit.")
    return result


def _bounded_component(value: str, *, limit: int) -> str:
    """Compact an oversized readable component while preserving its identity."""

    if len(value) <= limit:
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    prefix_limit = limit - len(digest) - 2
    prefix = value[:prefix_limit].rstrip(" ._") or "unnamed"
    return f"{prefix}__{digest}"


def _safe_filename_component(value: str) -> str:
    """Return a conservative filename component for generated artifacts."""

    replaced = _UNSAFE_FILENAME_COMPONENT_RE.sub("_", value.strip())
    replaced = re.sub(r"\s+", "_", replaced)
    collapsed = _FILENAME_SEPARATOR_RE.sub("_", replaced).strip(" ._")
    return collapsed or "unnamed"


def _safe_identity_component(value: str) -> str:
    """Return a component for graph identities that may contain path syntax."""

    normalized = value.strip()
    try:
        return _safe_filename_component(
            validate_top_level_name(normalized, subject="Graph identity")
        )
    except ValueError:
        safe_name = _safe_filename_component(normalized)
        identity_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
        return f"{safe_name}__{identity_hash}"


def _short_path_hash(path: Path) -> str:
    """Return a stable short hash for a normalized filesystem path."""

    try:
        normalized_path = path.expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        normalized_path = path.absolute()
    normalized = str(normalized_path).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]


def _image_size_component(image_size: tuple[int, int] | None) -> str:
    """Return deterministic dimensions text for bound mask filenames."""

    if image_size is None:
        return "unknown_size"
    width, height = image_size
    if width <= 0 or height <= 0:
        return "unknown_size"
    return f"{width}x{height}"


__all__ = ["MAX_BOUND_MASK_FILENAME_LENGTH", "bound_mask_filename"]
