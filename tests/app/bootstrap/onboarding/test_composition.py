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

"""Test bootstrap composition of onboarding runtime provisioning."""

from __future__ import annotations

from pathlib import Path

from substitute.app.bootstrap.installation_context import (
    build_onboarding_service_bundle,
)
from substitute.infrastructure.onboarding import SubstituteRuntimeProvisioner


def test_onboarding_service_bundle_wires_runtime_provisioner(tmp_path: Path) -> None:
    """Bootstrap bundle should compose the visible runtime provisioner."""

    bundle = build_onboarding_service_bundle(tmp_path)

    assert isinstance(bundle.runtime_service.provisioner, SubstituteRuntimeProvisioner)
