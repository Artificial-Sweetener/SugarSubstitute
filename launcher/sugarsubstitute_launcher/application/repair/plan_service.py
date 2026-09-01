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

"""Build fail-closed repair plans from installation and ownership facts."""

from __future__ import annotations

from pathlib import Path

from launcher.sugarsubstitute_launcher.application.repair.models import (
    ManagedComfyOwnership,
    RepairDisposition,
    RepairOperation,
    RepairPlan,
    RepairScope,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)

_COMFY_DIR_NAME = "comfyui"
_OWNED_NODE_DIR_NAMES = ("substitute-backend", "SugarCubes")
_COMFY_USER_DIR_NAMES = ("user", "models", "input", "output")


class RepairPlanError(RuntimeError):
    """Report repair requests whose ownership boundary cannot be proven safely."""


class RepairPlanService:
    """Own preservation and replacement policy for installer repair modes."""

    def build_application_plan(
        self,
        *,
        layout: InstallLayout,
        comfy_ownership: ManagedComfyOwnership | None = None,
    ) -> RepairPlan:
        """Plan a fresh application install while retaining authoritative user state."""

        root = layout.root.resolve()
        operations = [
            self._operation(
                root / ".repair",
                RepairDisposition.PRESERVE,
                "repair transaction state",
            ),
            self._operation(layout.user_dir, RepairDisposition.PRESERVE, "user files"),
            self._operation(
                layout.appdata_dir / "session",
                RepairDisposition.PRESERVE,
                "unsaved-work recovery state",
            ),
            self._operation(
                root / _COMFY_DIR_NAME,
                RepairDisposition.PRESERVE,
                "Comfy installation and models are outside application repair",
            ),
            self._operation(
                layout.app_dir, RepairDisposition.REPLACE, "application payload"
            ),
            self._operation(
                layout.runtime_dir, RepairDisposition.REPLACE, "application runtime"
            ),
            self._operation(
                layout.launcher_dir,
                RepairDisposition.QUARANTINE,
                "replaceable launcher state",
            ),
        ]
        launcher_target = launcher_bundle_target_for_key(layout.target.key)
        operations.extend(
            self._operation(
                root / replacement_root,
                RepairDisposition.REPLACE,
                "installed launcher bundle",
            )
            for replacement_root in launcher_target.replacement_roots
        )
        operations.extend(self._quarantine_unowned_root_entries(layout, operations))
        operations.extend(self._quarantine_replaceable_appdata(layout))
        if comfy_ownership is not None:
            comfy_root = self._verified_managed_comfy_root(layout, comfy_ownership)
            operations.extend(self._owned_node_operations(comfy_root))
        return self._plan(RepairScope.APPLICATION, root, operations)

    def build_owned_nodes_plan(
        self,
        *,
        layout: InstallLayout,
        comfy_ownership: ManagedComfyOwnership,
    ) -> RepairPlan:
        """Plan replacement of only the two custom-node packages owned by the app."""

        comfy_root = self._verified_managed_comfy_root(layout, comfy_ownership)
        return self._plan(
            RepairScope.OWNED_COMFY_NODES,
            layout.root.resolve(),
            list(self._owned_node_operations(comfy_root)),
        )

    def build_full_managed_comfy_plan(
        self,
        *,
        layout: InstallLayout,
        comfy_ownership: ManagedComfyOwnership,
        replacement_names: frozenset[str] = frozenset(),
    ) -> RepairPlan:
        """Plan managed Comfy replacement while preserving user and third-party data."""

        comfy_root = self._verified_managed_comfy_root(layout, comfy_ownership)
        operations: list[RepairOperation] = []
        for name in _COMFY_USER_DIR_NAMES:
            operations.append(
                self._operation(
                    comfy_root / name,
                    RepairDisposition.PRESERVE,
                    f"Comfy user-owned {name} data",
                )
            )
        custom_nodes = comfy_root / "custom_nodes"
        operations.append(
            self._operation(
                custom_nodes,
                RepairDisposition.PRESERVE,
                "third-party custom nodes",
            )
        )
        operations.extend(self._owned_node_operations(comfy_root))
        protected_names = {*_COMFY_USER_DIR_NAMES, "custom_nodes"}
        active_names = (
            {child.name for child in comfy_root.iterdir()}
            if comfy_root.exists()
            else set()
        )
        unsafe_replacement_names = replacement_names.intersection(protected_names)
        if unsafe_replacement_names:
            raise RepairPlanError(
                "Full Comfy candidate attempts to replace protected roots: "
                + ", ".join(sorted(unsafe_replacement_names))
            )
        for name in sorted((active_names | replacement_names) - protected_names):
            disposition = (
                RepairDisposition.REPLACE
                if name in replacement_names
                else RepairDisposition.QUARANTINE
            )
            operations.append(
                self._operation(
                    comfy_root / name,
                    disposition,
                    "fresh managed Comfy core or environment",
                )
            )
        return self._plan(
            RepairScope.FULL_MANAGED_COMFY, layout.root.resolve(), operations
        )

    @staticmethod
    def _verified_managed_comfy_root(
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> Path:
        """Return the workspace only when persisted ownership facts agree exactly."""

        expected = (layout.root / _COMFY_DIR_NAME).resolve()
        if (
            ownership.target_mode != "managed_local"
            or not ownership.install_owned
            or ownership.workspace_root is None
            or ownership.workspace_root.resolve() != expected
        ):
            raise RepairPlanError(
                "Comfy repair requires a proven installer-owned managed_local workspace."
            )
        return expected

    @staticmethod
    def _owned_node_operations(comfy_root: Path) -> tuple[RepairOperation, ...]:
        """Return exact replacement operations for app-owned custom nodes."""

        custom_nodes = comfy_root / "custom_nodes"
        return tuple(
            RepairPlanService._operation(
                custom_nodes / name,
                RepairDisposition.REPLACE,
                "SugarSubstitute-owned custom node",
            )
            for name in _OWNED_NODE_DIR_NAMES
        )

    @staticmethod
    def _quarantine_unowned_root_entries(
        layout: InstallLayout,
        declared_operations: list[RepairOperation],
    ) -> tuple[RepairOperation, ...]:
        """Quarantine unknown root content instead of deleting it silently."""

        if not layout.root.exists():
            return ()
        declared_roots = {operation.path for operation in declared_operations}
        declared_roots.add(layout.appdata_dir.resolve())
        return tuple(
            RepairPlanService._operation(
                child,
                RepairDisposition.QUARANTINE,
                "unknown installation-root content",
            )
            for child in layout.root.iterdir()
            if child.resolve() not in declared_roots
        )

    @staticmethod
    def _quarantine_replaceable_appdata(
        layout: InstallLayout,
    ) -> tuple[RepairOperation, ...]:
        """Quarantine non-session application state for fresh reconstruction."""

        if not layout.appdata_dir.exists():
            return ()
        return tuple(
            RepairPlanService._operation(
                child,
                RepairDisposition.QUARANTINE,
                "replaceable application state",
            )
            for child in layout.appdata_dir.iterdir()
            if child.name != "session"
        )

    @staticmethod
    def _operation(
        path: Path,
        disposition: RepairDisposition,
        reason: str,
    ) -> RepairOperation:
        """Build one normalized repair operation."""

        return RepairOperation(
            path=path.resolve(),
            disposition=disposition,
            reason=reason,
        )

    @staticmethod
    def _plan(
        scope: RepairScope,
        install_root: Path,
        operations: list[RepairOperation],
    ) -> RepairPlan:
        """Return a stable plan with duplicate path decisions rejected."""

        resolved_root = install_root.resolve()
        decisions: dict[Path, RepairDisposition] = {}
        for operation in operations:
            if not operation.path.is_relative_to(resolved_root):
                raise RepairPlanError(
                    f"Repair operation escapes installation root: {operation.path}"
                )
            previous = decisions.get(operation.path)
            if previous is not None and previous is not operation.disposition:
                raise RepairPlanError(
                    f"Conflicting repair decisions for {operation.path}: "
                    f"{previous.value} and {operation.disposition.value}."
                )
            decisions[operation.path] = operation.disposition
        ordered = tuple(
            sorted(
                dict.fromkeys(operations),
                key=lambda operation: (len(operation.path.parts), str(operation.path)),
            )
        )
        return RepairPlan(
            scope=scope,
            install_root=resolved_root,
            operations=ordered,
        )
