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

"""Tests for repair routing and repair-mode onboarding behavior."""

from __future__ import annotations

from pathlib import Path

from substitute.app.bootstrap.installation_context import (
    build_onboarding_service_bundle,
)
from substitute.domain.onboarding import BootstrapRoute, RuntimeBootstrapStatus
from substitute.infrastructure.onboarding import SubstituteRuntimeProvisioner


def test_readiness_service_routes_broken_runtime_to_repair(tmp_path: Path) -> None:
    """Missing runtime python should route bootstrap to repair instead of onboarding."""

    bundle = build_onboarding_service_bundle(tmp_path)
    installation = bundle.installation_service.save(
        bundle.installation_service.create_default()
    )
    bundle.runtime_service.save(
        type(bundle.runtime_service.create_default())(
            runtime_root=installation.runtime_dir,
            python_executable=installation.runtime_dir
            / ".venv"
            / "Scripts"
            / "python.exe",
            bootstrap_status=RuntimeBootstrapStatus.READY,
            schema_version="1",
        )
    )
    bundle.comfy_target_service.configure(bundle.comfy_target_service.create_default())

    assessment = bundle.readiness_service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert any(
        issue.code.value == "runtime_python_missing" for issue in assessment.issues
    )


def test_readiness_service_routes_missing_setup_to_onboarding(tmp_path: Path) -> None:
    """Missing persisted setup should route bootstrap to onboarding."""

    assessment = build_onboarding_service_bundle(tmp_path).readiness_service.assess()

    assert assessment.route is BootstrapRoute.ONBOARDING


def test_onboarding_service_bundle_wires_runtime_provisioner(tmp_path: Path) -> None:
    """Bootstrap bundle should compose the visible runtime provisioner."""

    bundle = build_onboarding_service_bundle(tmp_path)

    assert isinstance(bundle.runtime_service.provisioner, SubstituteRuntimeProvisioner)
