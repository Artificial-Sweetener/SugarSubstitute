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

"""Coordinate the production installer model checklist and gallery."""

from __future__ import annotations

from collections.abc import Callable, Collection

from PySide6.QtCore import QUrl, Slot
from PySide6.QtGui import QDesktopServices

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.ui.experience_models import (
    ModelCardPresentation,
)
from launcher.sugarsubstitute_launcher.ui.installer_view import InstallerView
from launcher.sugarsubstitute_launcher.ui.model_onboarding_execution import (
    QtModelOnboardingExecutor,
    require_discovery_plan,
)
from sugarsubstitute_shared.model_discovery import (
    CubeModelCapability,
    ModelDiscoveryPlan,
    ModelOnboardingService,
    model_card_identity,
)


class InstallerModelOnboardingController:
    """Own installer model flow state above reusable shared services and Qt pages."""

    def __init__(
        self,
        *,
        view: InstallerView,
        service: ModelOnboardingService,
        capabilities: Collection[CubeModelCapability],
        on_finished: Callable[[], None],
        executor: QtModelOnboardingExecutor,
    ) -> None:
        """Store model boundaries and connect production-page intent."""

        self._view = view
        self._service = service
        self._capabilities = tuple(capabilities)
        self._on_finished = on_finished
        self._executor = executor
        self._plan: ModelDiscoveryPlan | None = None
        self._completed = False
        self._active = False
        view.model_interest_page.continue_requested.connect(self._request_discovery)
        view.model_interest_page.skip_requested.connect(self._finish)
        view.model_gallery_page.back_requested.connect(self._show_interests)
        view.model_gallery_page.explore_requested.connect(self._explore)
        view.model_gallery_page.continue_requested.connect(
            self._request_download_or_finish
        )
        executor.plan_succeeded.connect(self._handle_plan)
        executor.download_succeeded.connect(self._handle_downloads)
        executor.failed.connect(self._handle_failure)

    @property
    def active(self) -> bool:
        """Return whether optional model onboarding currently owns the view."""

        return self._active

    def offer_if_eligible(self) -> bool:
        """Show the checklist only when no cube-compatible local model exists."""

        eligibility = self._service.assess(self._capabilities)
        if not eligibility.should_offer:
            return False
        self._active = True
        self._view.show_model_interests(eligibility.supported_categories)
        return True

    @Slot()
    def _request_discovery(self) -> None:
        """Fetch top monthly candidates for checked categories."""

        selected = self._view.model_interest_page.selected_categories
        if not selected:
            self._view.model_interest_page.set_status(
                launcher_text("Choose at least one model type, or skip model setup."),
                working=False,
            )
            return
        self._view.model_interest_page.set_status(
            launcher_text("Finding safe popular models from the last month..."),
            working=True,
        )
        self._executor.start_plan(
            service=self._service,
            capabilities=self._capabilities,
            selected_categories=selected,
        )

    @Slot(object)
    def _handle_plan(self, result: object) -> None:
        """Render unchecked cards from a completed discovery plan."""

        plan = require_discovery_plan(result)
        self._plan = plan
        cards = tuple(
            ModelCardPresentation(
                category=card.model.category,
                model_name=card.model.model_name,
                version_name=card.model.version_name,
                creator=card.model.creator,
                base_model=card.model.base_model,
                size_bytes=card.model.size_bytes,
                destination=card.destination,
                thumbnail_url=card.model.thumbnail_url,
                provider_identity=model_card_identity(card),
            )
            for card in plan.cards
        )
        self._view.show_model_gallery(cards)
        if not cards:
            self._view.model_gallery_page.set_status(
                launcher_text(
                    "No safe downloadable matches are available right now. You can skip or explore CivitAI."
                ),
                working=False,
            )
        else:
            self._view.model_gallery_page.set_status("", working=False)

    @Slot()
    def _request_download_or_finish(self) -> None:
        """Download checked cards, or continue after completion or no selection."""

        if self._completed:
            self._finish()
            return
        plan = self._plan
        if plan is None:
            return
        selected = self._view.model_gallery_page.selected_model_ids
        if not selected:
            self._finish()
            return
        self._view.model_gallery_page.set_status(
            launcher_text(
                "Downloading %1 selected model file(s). Existing files will not be overwritten.",
                len(selected),
            ),
            working=True,
        )
        self._executor.start_download(
            service=self._service,
            plan=plan,
            selected_identities=selected,
        )

    @Slot(object)
    def _handle_downloads(self, value: object) -> None:
        """Show verified acquisition completion before returning to setup."""

        if not isinstance(value, tuple):
            self._handle_failure(
                launcher_text("Model downloads returned invalid results.")
            )
            return
        self._completed = True
        self._view.model_gallery_page.set_status(
            launcher_text(
                "%1 model file(s) downloaded and verified. You can continue setup.",
                len(value),
            ),
            working=False,
            completed=True,
        )

    @Slot(str)
    def _handle_failure(self, details: str) -> None:
        """Keep model onboarding optional after discovery or transfer failure."""

        if self._plan is None:
            self._view.model_interest_page.set_status(
                launcher_text(
                    "Popular models could not be loaded. You can retry or skip. Details: %1",
                    details,
                ),
                working=False,
            )
            return
        self._view.model_gallery_page.set_status(
            launcher_text(
                "Model downloads did not finish. Existing models were unchanged. Details: %1",
                details,
            ),
            working=False,
        )

    @Slot()
    def _show_interests(self) -> None:
        """Return to the category checklist without provider work."""

        eligibility = self._service.assess(self._capabilities)
        self._view.show_model_interests(eligibility.supported_categories)

    @Slot()
    def _explore(self) -> None:
        """Open the public provider browse page with no secret query data."""

        if self._plan is not None:
            QDesktopServices.openUrl(QUrl(self._plan.explore_url))

    @Slot()
    def _finish(self) -> None:
        """End optional onboarding and return control to installation progress."""

        self._view.show_install_location()
        self._active = False
        self._on_finished()


__all__ = ["InstallerModelOnboardingController"]
