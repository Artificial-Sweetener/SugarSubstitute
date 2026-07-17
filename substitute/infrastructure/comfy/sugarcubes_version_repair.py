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

"""Repair approved SugarCubes custom-node revisions through libgit2."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import re

from substitute.infrastructure.comfy.nodepack_manifest import (
    SUGARCUBES_BASE_NODEPACK_INSTALLS,
    SugarCubesNodepackInstallCandidate,
)
from substitute.infrastructure.comfy.nodepack_python_dependencies import (
    install_nodepack_requirements,
)
from substitute.infrastructure.comfy.nodepack_reconciliation_logger import (
    LogCallback,
    emit_log,
)
from substitute.infrastructure.version_control import (
    RepositoryOperationError,
    RepositoryService,
    repository_service,
)

_GIT_COMMIT_PATTERN = re.compile(r"[0-9a-fA-F]{40}")


def repair_sugarcubes_git_versions(
    payload: Mapping[str, object],
    *,
    workspace: Path,
    python_executable: Path,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
    repositories: RepositoryService | None = None,
) -> bool:
    """Checkout safe known revision repairs reported by SugarCubes maintenance."""

    selected = repositories or repository_service()
    repaired = False
    for item in _version_plan(payload):
        if item.get("status") != "installed_commit_not_descendant":
            continue
        if item.get("repairable") is not True:
            continue
        node_id = _string(item.get("nodeId"))
        revision = _string(item.get("requiredVersion"))
        evidence = item.get("installedEvidence")
        if not isinstance(evidence, Mapping):
            raise RuntimeError(
                f"SugarCubes revision evidence is missing for {node_id}."
            )
        candidate = _candidate_for(node_id)
        target_path = workspace / "custom_nodes" / candidate.target_folder_name
        if not _GIT_COMMIT_PATTERN.fullmatch(revision):
            raise RuntimeError(
                f"SugarCubes reported an invalid revision for {node_id}."
            )
        if evidence.get("dirty") is True:
            raise RuntimeError(
                f"SugarCubes cannot update dirty custom-node checkout {node_id}."
            )
        if _string(evidence.get("sourceKind")) != "git":
            raise RuntimeError(f"SugarCubes reported a non-git source for {node_id}.")
        if _normalized_url(_string(evidence.get("repositoryUrl"))) != _normalized_url(
            candidate.source_url
        ):
            raise RuntimeError(
                f"SugarCubes repository provenance does not match {node_id}."
            )
        if Path(_string(evidence.get("sourcePath"))).resolve() != target_path.resolve():
            raise RuntimeError(f"SugarCubes source path does not match {node_id}.")
        try:
            selected.fetch_all(target_path, on_progress=on_log)
            selected.checkout_revision(target_path, revision)
        except RepositoryOperationError as error:
            emit_log(
                on_log,
                (
                    f"[SugarCubes] Could not move {node_id} to optional cube "
                    f"revision {revision}: {error}"
                ),
                operation="sugarcubes_version_repair",
                node_id=node_id,
                required_revision=revision,
            )
            continue
        install_nodepack_requirements(
            python_executable=python_executable,
            nodepack_root=target_path,
            display_name=node_id,
            on_log=on_log,
            env=env,
        )
        repaired = True
    return repaired


def _version_plan(payload: Mapping[str, object]) -> Sequence[Mapping[str, object]]:
    """Return the latest readiness version plan from a maintenance payload."""

    repair_result = payload.get("repairResult")
    if isinstance(repair_result, Mapping):
        readiness = repair_result.get("readinessAfter")
    else:
        readiness = payload.get("dependencyReadiness")
    if not isinstance(readiness, Mapping):
        return ()
    plan = readiness.get("dependencyVersionPlan")
    if not isinstance(plan, Sequence) or isinstance(plan, (str, bytes)):
        return ()
    return tuple(item for item in plan if isinstance(item, Mapping))


def _candidate_for(node_id: str) -> SugarCubesNodepackInstallCandidate:
    """Return the one trusted repository candidate for a known SugarCubes node."""

    candidates = SUGARCUBES_BASE_NODEPACK_INSTALLS.get(node_id)
    if not candidates or len(candidates) != 1:
        raise RuntimeError(
            f"SugarCubes reported an unknown revision repair: {node_id}."
        )
    return candidates[0]


def _string(value: object) -> str:
    """Normalize one untrusted maintenance value to text."""

    return value.strip() if isinstance(value, str) else ""


def _normalized_url(value: str) -> str:
    """Normalize one trusted repository URL for exact provenance comparison."""

    return value.rstrip("/").casefold()


__all__ = ["repair_sugarcubes_git_versions"]
