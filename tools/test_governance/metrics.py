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

"""Own stable fingerprints for reviewed test-governance facts."""

from __future__ import annotations

import hashlib
from pathlib import Path

from tools.architecture_governance.metrics import source_fingerprint

_INVENTORY_RULES = frozenset({"ISOLATED001", "LAYOUT001", "SERIAL001", "STUB001"})


def reviewed_state_fingerprint(
    root: Path,
    *,
    rule: str,
    candidates: tuple[str, ...],
    paths: tuple[str, ...],
) -> str:
    """Fingerprint the exact fact whose reviewed disposition must remain stable."""

    if rule not in _INVENTORY_RULES:
        return source_fingerprint(root, paths)
    digest = hashlib.sha256()
    for candidate in sorted(candidates):
        digest.update(candidate.encode("utf-8"))
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"
