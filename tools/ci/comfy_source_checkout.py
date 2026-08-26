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

"""Materialize exact Comfy workspaces from verified local source objects."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from tools.ci.comfy_probe_support import git_output, run_checked
from tools.ci.comfy_support_matrix import (
    COMFY_RELEASE_CONTRACTS,
    ComfySupportMatrixEntry,
)


def prepare_checkout(
    workspace: Path,
    tag: str,
    *,
    source_repository: Path,
    contracts: Sequence[ComfySupportMatrixEntry] = COMFY_RELEASE_CONTRACTS,
) -> None:
    """Materialize a fresh exact-tag workspace from verified local objects."""

    resolved_workspace = workspace.resolve()
    resolved_source_repository = source_repository.resolve()
    entry = _contract_for_tag(tag, contracts)
    if resolved_workspace.is_dir():
        actual_tag = git_output(
            resolved_workspace,
            "describe",
            "--tags",
            "--exact-match",
        )
        actual_commit = git_output(resolved_workspace, "rev-parse", "HEAD")
        if actual_tag != tag or actual_commit != entry.commit_sha:
            raise RuntimeError(
                "Existing compatibility workspace is "
                f"{actual_tag!r} at {actual_commit!r}; expected "
                f"{tag!r} at {entry.commit_sha!r}."
            )
        return
    source_commit = git_output(
        resolved_source_repository,
        "rev-parse",
        f"refs/tags/{tag}^{{commit}}",
    )
    if source_commit != entry.commit_sha:
        raise RuntimeError(
            f"Verified source repository provides {tag!r} at {source_commit!r}; "
            f"expected {entry.commit_sha!r}."
        )
    resolved_workspace.parent.mkdir(parents=True, exist_ok=True)
    run_checked(
        [
            "git",
            "clone",
            "--no-checkout",
            "--no-hardlinks",
            str(resolved_source_repository),
            str(resolved_workspace),
        ],
        cwd=resolved_workspace.parent,
        timeout_seconds=60,
    )
    checkout_tag(resolved_workspace, tag, contracts=contracts)


def checkout_tag(
    workspace: Path,
    tag: str,
    *,
    contracts: Sequence[ComfySupportMatrixEntry] = COMFY_RELEASE_CONTRACTS,
) -> None:
    """Switch to one locally available reviewed tag without remote access."""

    resolved_workspace = workspace.resolve()
    entry = _contract_for_tag(tag, contracts)
    run_checked(
        ["git", "checkout", "--detach", tag],
        cwd=resolved_workspace,
        timeout_seconds=60,
    )
    actual_commit = git_output(resolved_workspace, "rev-parse", "HEAD")
    if actual_commit != entry.commit_sha:
        raise RuntimeError(
            f"Checked out {tag!r} at {actual_commit!r}; expected {entry.commit_sha!r}."
        )


def _contract_for_tag(
    tag: str,
    contracts: Sequence[ComfySupportMatrixEntry],
) -> ComfySupportMatrixEntry:
    """Return one exact contract from the supplied immutable source registry."""

    for contract in contracts:
        if contract.comfyui_tag == tag:
            return contract
    supported = ", ".join(contract.comfyui_tag for contract in contracts)
    raise ValueError(f"Unknown Comfy source tag {tag!r}; expected {supported}.")


__all__ = ["checkout_tag", "prepare_checkout"]
