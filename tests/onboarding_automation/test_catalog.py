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

"""Verify onboarding automation scenario discovery and entrypoint resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.onboarding_automation.driver import resolve_scenario_entrypoint
from tests.onboarding_automation.external_comfy_fixture import build_external_fixture
from tests.onboarding_automation.fixture_paths import resolve_scenario_paths
from tests.onboarding_automation.fixture_owner import OnboardingScenarioFixtureOwner
from tests.onboarding_automation.scenarios import ScenarioDefinition, build_scenarios


_FAILURE_STAGE_ENV = "SUGARSUB_FORCE_MANAGED_FAILURE_STAGE"


def _build_scenario_catalog(tmp_path: Path) -> dict[str, ScenarioDefinition]:
    """Build one catalog with a deterministic run-owned external fixture."""

    paths = resolve_scenario_paths(tmp_path)
    return build_scenarios(
        paths,
        external_fixture=build_external_fixture(paths, port_factory=lambda: 49152),
    )


def test_scenario_catalog_includes_failure_and_recovery_coverage(
    tmp_path: Path,
) -> None:
    """Expose the complete real failure and recovery campaign."""

    scenarios = _build_scenario_catalog(tmp_path)

    assert "managed_stale_bootstrap_recovery_real" in scenarios
    assert "managed_clone_failure_real" in scenarios
    assert "managed_retry_after_clone_failure_real" in scenarios
    assert "managed_dependency_failure_real" in scenarios
    assert "attached_missing_workspace_real" in scenarios
    assert "attached_unreachable_real" in scenarios
    attached = scenarios["attached_clean_real"]
    assert attached.external_fixture is not None
    assert attached.endpoint_port == attached.external_fixture.endpoint.port
    assert attached.attached_workspace_path == attached.external_fixture.workspace_root


def test_real_scenario_entrypoint_uses_the_resolved_app_layout(
    tmp_path: Path,
) -> None:
    """Resolve the real application entrypoint from an arbitrary install root."""

    entrypoint = resolve_scenario_entrypoint(tmp_path)

    assert entrypoint.is_file()
    assert entrypoint.name == "main.py"


def test_scenario_fixture_restores_the_callers_failure_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Restore ambient failure injection after an isolated scenario lifecycle."""

    scenario = _build_scenario_catalog(tmp_path)["ui_smoke_managed"]
    monkeypatch.setenv(_FAILURE_STAGE_ENV, "callers-stage")
    owner = OnboardingScenarioFixtureOwner(scenario)

    owner.prepare()
    assert _FAILURE_STAGE_ENV not in os.environ

    owner.close()
    assert os.environ[_FAILURE_STAGE_ENV] == "callers-stage"
