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

"""Expose opt-in usage-aware model update services."""

from sugarsubstitute_shared.model_updates.acquisition import (
    ModelUpdateAcquisitionService,
    model_update_identity,
)
from sugarsubstitute_shared.model_updates.civitai_gateway import (
    CivitaiCompatibleUpdateGateway,
)
from sugarsubstitute_shared.model_updates.models import (
    ModelUpdatePreferences,
    ModelUpdateProposal,
    ModelUsageRecord,
)
from sugarsubstitute_shared.model_updates.service import ModelUpdateService

__all__ = [
    "ModelUpdateAcquisitionService",
    "ModelUpdatePreferences",
    "ModelUpdateProposal",
    "ModelUpdateService",
    "ModelUsageRecord",
    "CivitaiCompatibleUpdateGateway",
    "model_update_identity",
]
