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

"""Stage a sealed selected generation for replacement of its retained root."""

from __future__ import annotations

from pathlib import Path
import shutil
from uuid import uuid4

from sugarsubstitute_shared.installation_mutation import installation_mutation
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
    SelectedLauncherBundle,
)
from sugarsubstitute_shared.launcher_update.bundle_validation import (
    validate_launcher_bundle,
)
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.targets import LauncherBundleTarget


class LauncherBaselineRefreshStager:
    """Copy one verified generation into independent baseline-update staging."""

    def stage(
        self,
        *,
        install_root: Path,
        selected: SelectedLauncherBundle,
        target: LauncherBundleTarget,
    ) -> Path:
        """Return a durable request only while the selected generation stays sealed."""

        root = install_root.resolve()
        if selected.generation is None or selected.version is None:
            raise ValueError(
                "Baseline refresh requires a selected launcher generation."
            )
        update_root = root / "launcher" / "updates"
        attempt_root = update_root / "staging" / "baseline-refresh" / uuid4().hex
        with installation_mutation(root):
            selection = LauncherBundleSelection(root, target)
            if selection.resolve() != selected:
                raise ValueError("Selected launcher changed before baseline staging.")
            try:
                attempt_root.mkdir(parents=True)
                payload = attempt_root / "payload"
                shutil.copytree(selected.root, payload, symlinks=True)
                validate_launcher_bundle(bundle_dir=payload, target=target)
                selection.require_matching_staged_copy(selected, payload)
                if selection.resolve() != selected:
                    raise ValueError(
                        "Selected launcher changed during baseline staging."
                    )
                request_path = attempt_root / "request.json"
                LauncherUpdateRequest(
                    install_root=root,
                    version=selected.version,
                    target_key=target.key,
                    staged_bundle_dir=payload,
                    relaunch=False,
                ).save(request_path)
                return request_path
            except BaseException:
                shutil.rmtree(attempt_root, ignore_errors=True)
                raise


__all__ = ["LauncherBaselineRefreshStager"]
