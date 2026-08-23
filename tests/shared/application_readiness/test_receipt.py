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

"""Test shared compatibility behavior for readiness receipts."""

from __future__ import annotations

from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
    READINESS_SCHEMA_VERSION,
)


def test_legacy_readiness_receipt_remains_parseable_but_not_main_shell() -> None:
    """Parse schema-one evidence without claiming main-shell readiness."""

    receipt = ApplicationReadinessReceipt.from_json(
        {"pid": 123, "schema_version": 1, "token": "legacy-token"}
    )

    assert READINESS_SCHEMA_VERSION > 1
    assert receipt.surface is ApplicationReadinessSurface.LEGACY_VISIBLE_SHELL
