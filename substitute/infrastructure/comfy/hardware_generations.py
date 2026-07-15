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

"""Infer stable accelerator-generation hints from human-readable adapter names."""

from __future__ import annotations

import re


def infer_generation_hint(adapter_name: str) -> str | None:
    """Return the install-policy generation represented by one adapter name."""

    normalized = adapter_name.lower()
    if re.search(r"\brtx\s*50\d{2}\b", normalized):
        return "blackwell"
    if re.search(r"\brtx\s*40\d{2}\b", normalized):
        return "ada"
    if re.search(r"\brtx\s*30\d{2}\b", normalized):
        return "ampere"
    if re.search(r"\bradeon\s+rx\s*9\d{3}\b", normalized):
        return "rdna4"
    if re.search(r"\bradeon\s+rx\s*7\d{3}\b", normalized):
        return "rdna3"
    if (
        "ryzen ai max" in normalized
        or "strix halo" in normalized
        or re.search(r"\bradeon\s+80(?:50|60)s\b", normalized)
    ):
        return "rdna3.5"
    if "intel" in normalized and "arc" in normalized:
        return "intel_xpu"
    return None


__all__ = ["infer_generation_hint"]
