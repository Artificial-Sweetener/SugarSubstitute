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

"""Qualify the exact reusable Comfy source-input workflow owner."""

from __future__ import annotations

from tests.qualification.release.workflow.support import (
    PROJECT_ROOT,
    action_step,
    assert_trusted_cache_policy,
    load_action,
    workflow_consumers,
)


_COMFY_SOURCE_CACHE_CONSUMERS = {
    "comfy-runtime-compatibility.yml",
    "comfy-update-compatibility.yml",
    "release-update-qualification.yml",
}


def test_comfy_source_cache_has_one_portable_exact_owner() -> None:
    """Reuse reviewed upstream Git objects without caching mutable workspaces."""

    reference = "./.github/actions/prepare-comfy-source-cache"
    assert workflow_consumers(reference) == _COMFY_SOURCE_CACHE_CONSUMERS
    action = load_action("prepare-comfy-source-cache")
    identity = str(action_step(action, "Resolve Comfy source-cache identity")["run"])
    assert "tools/ci/comfy_support_matrix.py" in identity
    assert "$matrixHash" in identity
    assert '"primary-key=comfy-source-v1-$matrixHash"' in identity
    assert_trusted_cache_policy(
        action,
        "Restore trusted Comfy source cache",
        "Restore untrusted Comfy source cache read-only",
    )
    trusted_inputs = action_step(
        action,
        "Restore trusted Comfy source cache",
    )["with"]
    untrusted_inputs = action_step(
        action,
        "Restore untrusted Comfy source cache read-only",
    )["with"]
    assert isinstance(trusted_inputs, dict)
    assert isinstance(untrusted_inputs, dict)
    assert set(trusted_inputs) == {"path", "key", "enableCrossOsArchive"}
    assert set(untrusted_inputs) == {"path", "key", "enableCrossOsArchive"}
    assert trusted_inputs["enableCrossOsArchive"] is True
    assert untrusted_inputs["enableCrossOsArchive"] is True
    assert "restore-keys" not in trusted_inputs
    assert "restore-keys" not in untrusted_inputs

    for workflow_name in (
        "comfy-runtime-compatibility.yml",
        "comfy-update-compatibility.yml",
    ):
        workflow_text = (
            PROJECT_ROOT / ".github" / "workflows" / workflow_name
        ).read_text(encoding="utf-8")
        assert workflow_text.index(reference) < workflow_text.index(
            "Run exact upstream"
        )
        assert '--source-cache "${{ steps.comfy-source.outputs.cache-path }}"' in (
            workflow_text
        )
    update_workflow = (
        PROJECT_ROOT / ".github" / "workflows" / "release-update-qualification.yml"
    ).read_text(encoding="utf-8")
    assert update_workflow.index(reference) < update_workflow.index(
        "Prove historical update"
    )
    assert '--source-cache "${{ steps.comfy-source.outputs.cache-path }}"' in (
        update_workflow
    )


def test_comfy_source_cache_excludes_mutable_or_release_state() -> None:
    """Persist only immutable Git inputs under one disposable cache namespace."""

    action = load_action("prepare-comfy-source-cache")
    source_inputs = action["inputs"]
    assert isinstance(source_inputs, dict)
    source_path = source_inputs["cache-path"]
    assert isinstance(source_path, dict)
    assert source_path["default"] == "build/comfy-source-cache"
    forbidden = (
        ".venv",
        "node_modules",
        ".local-release-channel",
        "build/release",
        "artifact",
        "candidate",
        "credential",
        "secret",
        "signing",
    )
    assert all(
        fragment not in str(source_path["default"]).lower() for fragment in forbidden
    )
