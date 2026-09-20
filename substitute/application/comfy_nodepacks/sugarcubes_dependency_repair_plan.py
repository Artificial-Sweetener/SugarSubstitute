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

"""Select SugarCubes-reported dependencies for authoritative repair."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.comfy_nodepacks.sugarcubes_maintenance_report_parser import (
    current_dependency_readiness,
    mapping_items,
    string_value,
)


def dependency_repair_node_ids(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Return every missing or version-deficient node pack SugarCubes can repair."""

    readiness = current_dependency_readiness(payload)
    if readiness is None:
        return ()
    node_ids: list[str] = []
    for item in mapping_items(readiness.get("installPlan")):
        node_id = string_value(item.get("nodeId"))
        if (
            node_id
            and item.get("installed") is not True
            and item.get("installable") is True
        ):
            node_ids.append(node_id)
    for item in mapping_items(readiness.get("dependencyVersionPlan")):
        node_id = string_value(item.get("nodeId"))
        if (
            node_id
            and item.get("status") != "satisfied"
            and item.get("repairable") is True
        ):
            node_ids.append(node_id)
    return tuple(dict.fromkeys(node_ids))


__all__ = ["dependency_repair_node_ids"]
