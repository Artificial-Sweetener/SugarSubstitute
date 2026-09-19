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

"""Resolve genuine workflow files from Comfy's installed template catalog."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path


def load_workflow_template_paths(template_root: Path) -> tuple[Path, ...]:
    """Return catalogued workflow JSON without admitting package metadata."""

    catalog_path = template_root / "index.json"
    payload: object = json.loads(catalog_path.read_text(encoding="utf-8"))
    names = _collect_template_names(payload)
    if not names:
        raise ValueError(f"Comfy workflow template catalog is empty: {catalog_path}")
    if len(set(names)) != len(names):
        raise ValueError(
            f"Comfy workflow template catalog has duplicate names: {catalog_path}"
        )
    paths = tuple(sorted(template_root / f"{name}.json" for name in names))
    missing = tuple(path for path in paths if not path.is_file())
    if missing:
        raise FileNotFoundError(
            "Comfy workflow template catalog references missing files: "
            + ", ".join(path.name for path in missing)
        )
    return paths


def _collect_template_names(payload: object) -> tuple[str, ...]:
    """Collect workflow names only from catalog-owned template collections."""

    names: list[str] = []
    if isinstance(payload, Mapping):
        templates = payload.get("templates")
        if isinstance(templates, Sequence) and not isinstance(templates, (str, bytes)):
            for template in templates:
                if isinstance(template, Mapping) and isinstance(
                    template.get("name"), str
                ):
                    names.append(str(template["name"]))
        for value in payload.values():
            names.extend(_collect_template_names(value))
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for value in payload:
            names.extend(_collect_template_names(value))
    return tuple(names)


__all__ = ["load_workflow_template_paths"]
