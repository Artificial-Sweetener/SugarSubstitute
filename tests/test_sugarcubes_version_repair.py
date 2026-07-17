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

"""Tests for libgit2-backed SugarCubes revision repair."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.infrastructure.comfy import sugarcubes_version_repair
from substitute.infrastructure.comfy.nodepack_manifest import (
    SUGARCUBES_BASE_NODEPACK_INSTALLS,
)
from tests.repository_service_test_double import RecordingRepositoryService


def test_sugarcubes_version_repair_fetches_and_checks_out_known_revision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A safe known version plan should use RepositoryService instead of git.exe."""

    node_id = "seedvr2_videoupscaler"
    candidate = SUGARCUBES_BASE_NODEPACK_INSTALLS[node_id][0]
    target = tmp_path / "custom_nodes" / candidate.target_folder_name
    (target / ".git").mkdir(parents=True)
    revision = "2a873e2f286224bb00c60fe3fb61b88b65258a6d"
    dependency_installs: list[Path] = []
    monkeypatch.setattr(
        sugarcubes_version_repair,
        "install_nodepack_requirements",
        lambda **kwargs: dependency_installs.append(kwargs["nodepack_root"]),
    )
    repositories = RecordingRepositoryService()
    payload = {
        "repairResult": {
            "readinessAfter": {
                "dependencyVersionPlan": [
                    {
                        "nodeId": node_id,
                        "requiredVersion": revision,
                        "status": "installed_commit_not_descendant",
                        "repairable": True,
                        "installedEvidence": {
                            "sourcePath": str(target),
                            "sourceKind": "git",
                            "repositoryUrl": candidate.source_url,
                            "dirty": False,
                        },
                    }
                ]
            }
        }
    }

    repaired = sugarcubes_version_repair.repair_sugarcubes_git_versions(
        payload,
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
        repositories=repositories,
    )

    assert repaired is True
    assert repositories.calls == [
        ("fetch_all", target),
        ("checkout_revision", (target, revision)),
    ]
    assert dependency_installs == [target]


def test_sugarcubes_version_repair_rejects_unexpected_repository(
    tmp_path: Path,
) -> None:
    """Maintenance output cannot redirect a trusted repair to another repository."""

    node_id = "seedvr2_videoupscaler"
    candidate = SUGARCUBES_BASE_NODEPACK_INSTALLS[node_id][0]
    target = tmp_path / "custom_nodes" / candidate.target_folder_name
    payload = {
        "dependencyReadiness": {
            "dependencyVersionPlan": [
                {
                    "nodeId": node_id,
                    "requiredVersion": "2a873e2f286224bb00c60fe3fb61b88b65258a6d",
                    "status": "installed_commit_not_descendant",
                    "repairable": True,
                    "installedEvidence": {
                        "sourcePath": str(target),
                        "sourceKind": "git",
                        "repositoryUrl": "https://example.invalid/attacker.git",
                        "dirty": False,
                    },
                }
            ]
        }
    }

    with pytest.raises(RuntimeError, match="provenance"):
        sugarcubes_version_repair.repair_sugarcubes_git_versions(
            payload,
            workspace=tmp_path,
            python_executable=tmp_path / "python.exe",
            repositories=RecordingRepositoryService(),
        )
