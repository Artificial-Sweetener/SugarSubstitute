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

"""Verify managed Comfy evidence policy across install and update paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sugarsubstitute_shared.installer_qualification import (
    InstallerQualificationPlan,
)
from substitute.domain.comfy_nodepacks import (
    SUGARCUBES_REQUIRED_VERSION,
    SUBSTITUTE_BACKEND_REQUIRED_VERSION,
)
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
)
from tools.ci import managed_comfy_qualification
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.managed_comfy_qualification import assert_real_managed_comfy


def test_historical_update_accepts_retained_setup_evidence_generations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Historical updates should validate live state, not fresh-cache cardinality."""

    plan = _managed_plan(tmp_path)
    _write_managed_runtime(plan)
    _write_setup_records(plan, "historical", "candidate")
    monkeypatch.setattr(
        managed_comfy_qualification,
        "_get_json",
        lambda url: _managed_response(url, plan),
    )

    assert_real_managed_comfy(
        install_root=plan.install_root,
        plan=plan,
        require_governed_setup_record=False,
    )


def test_fresh_install_rejects_multiple_setup_evidence_generations(
    tmp_path: Path,
) -> None:
    """Fresh installation proof should continue to require one setup generation."""

    plan = _managed_plan(tmp_path)
    _write_managed_runtime(plan)
    _write_setup_records(plan, "first", "second")

    with pytest.raises(InstallerLifecycleError, match="overlapping"):
        assert_real_managed_comfy(install_root=plan.install_root, plan=plan)


def _managed_plan(tmp_path: Path) -> InstallerQualificationPlan:
    """Build one managed-local qualification plan."""

    return InstallerQualificationPlan(
        token="qualification-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=48188,
        event_log_path=(tmp_path / "events.jsonl").resolve(),
        timeout_seconds=45.0,
        target_mode="managed_local",
        managed_workspace_path=(tmp_path / "comfyui").resolve(),
        managed_model_root=(tmp_path / "models").resolve(),
        force_cpu_mode=True,
    )


def _write_managed_runtime(plan: InstallerQualificationPlan) -> None:
    """Create the filesystem evidence required before live endpoint checks."""

    assert plan.managed_workspace_path is not None
    main_path = workspace_main_path(plan.managed_workspace_path)
    python_path = workspace_python_path(plan.managed_workspace_path)
    main_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    main_path.touch()
    python_path.touch()
    (plan.install_root / "appdata" / "runtime_state").mkdir(parents=True)


def _write_setup_records(
    plan: InstallerQualificationPlan,
    *generations: str,
) -> None:
    """Write successful retained cache generations beneath the managed workspace."""

    assert plan.managed_workspace_path is not None
    evidence_root = (
        plan.managed_workspace_path
        / ".substitute"
        / "cache"
        / "managed"
        / "managed-comfy"
        / "setup-evidence"
    )
    for generation in generations:
        generation_path = evidence_root / generation
        generation_path.mkdir(parents=True)
        (generation_path / "record.json").write_text(
            json.dumps({"success": True}),
            encoding="utf-8",
        )


def _managed_response(
    url: str,
    plan: InstallerQualificationPlan,
) -> dict[str, object]:
    """Return complete live managed-Comfy evidence for one endpoint route."""

    assert plan.managed_model_root is not None
    if url.endswith("/system_stats"):
        return {"system": {"comfyui_version": "0.28.2"}}
    if url.endswith("/object_info"):
        return {
            name: {}
            for name in (
                "SimpleSyrup.ResizeImageToTarget",
                "SimpleSyrup.ScaleFactor",
                "SimpleSyrup.VAEDecodeOptions",
                "SimpleSyrup.VAEEncodeOptions",
                "UpscaleModelLoader",
            )
        }
    if url.endswith("/substitute/v1/capabilities"):
        return {
            "extensionVersion": SUBSTITUTE_BACKEND_REQUIRED_VERSION,
            "cubeLibrary": {"sugarCubesVersion": SUGARCUBES_REQUIRED_VERSION},
        }
    model_root = str(plan.managed_model_root.resolve())
    return {"configuredModelRoot": model_root, "activeModelRoot": model_root}
