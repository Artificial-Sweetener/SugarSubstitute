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

"""Expose verified standalone Comfy environment provisioning services."""

from substitute.infrastructure.comfy.standalone_environment.catalog_client import (
    StandaloneEnvironmentCatalogClient,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArchiveKind,
    StandaloneArtifact,
    StandaloneEnvironmentRelease,
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.standalone_environment.variant_policy import (
    standalone_variant_for_target,
)

__all__ = [
    "StandaloneArchiveKind",
    "StandaloneArtifact",
    "StandaloneEnvironmentCatalogClient",
    "StandaloneEnvironmentRelease",
    "StandaloneVariantId",
    "standalone_variant_for_target",
]
