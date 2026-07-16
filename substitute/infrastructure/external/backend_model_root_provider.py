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

"""Adapt connected BackEnd model-root state into onboarding."""

from __future__ import annotations

from substitute.domain.comfy_environment import ComfyModelRootStatus
from substitute.domain.onboarding import ComfyTargetConfiguration
from substitute.infrastructure.external.substitute_backend_environment_client import (
    SubstituteBackendEnvironmentClient,
)


class BackendModelRootProvider:
    """Read model-root state from the Comfy endpoint selected by onboarding."""

    def load(
        self,
        target: ComfyTargetConfiguration,
    ) -> ComfyModelRootStatus | None:
        """Return host state only when BackEnd advertises the capability."""

        client = SubstituteBackendEnvironmentClient(target.endpoint)
        capabilities = client.get_environment_capabilities()
        if capabilities is None or not capabilities.model_root_management_supported:
            return None
        return client.get_model_root()


__all__ = ["BackendModelRootProvider"]
