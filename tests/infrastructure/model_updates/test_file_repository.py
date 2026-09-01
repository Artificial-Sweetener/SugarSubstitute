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

"""Verify authoritative model update state persistence and corruption handling."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from substitute.infrastructure.model_updates import (
    FileModelUsageRepository,
    ModelUpdateStateError,
)
from sugarsubstitute_shared.model_discovery.models import ModelCategory
from sugarsubstitute_shared.model_updates import (
    ModelUsageRecord,
)


def test_usage_round_trips_under_authoritative_user_settings(
    tmp_path: Path,
) -> None:
    """Generate usage should persist as authoritative state, not cache."""

    usage = FileModelUsageRepository(tmp_path)
    record = ModelUsageRecord(
        sha256="a" * 64,
        path=tmp_path / "models" / "model.safetensors",
        category=ModelCategory.CHECKPOINTS,
        model_id=1,
        version_id=2,
        base_model="SDXL",
        usage_count=3,
        last_used_at=datetime(2026, 8, 31, tzinfo=UTC),
    )

    usage.save((record,))

    assert usage.load() == (record,)


def test_corrupt_usage_is_not_silently_replaced_with_empty_state(
    tmp_path: Path,
) -> None:
    """Unreadable authoritative state should be visible rather than treated as cache miss."""

    (tmp_path / "model_usage.json").write_text("not-json", encoding="utf-8")

    with pytest.raises(ModelUpdateStateError, match="unreadable"):
        FileModelUsageRepository(tmp_path).load()
