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

"""Coordinate missing-family recommendations without owning provider rules."""

from __future__ import annotations

from collections.abc import Callable

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.localization import apply_application_text

from substitute.application.model_recommendations import (
    FamilyRecommendationPage,
    ModelInstallRecipePlanner,
    RecommendationCardAsset,
    RecommendationLinkResult,
    RecommendationLinkStatus,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelFamilyScanResult,
    ModelFamilyScanStatus,
)
from substitute.presentation.localization import LocalizedPrimaryPushButton
from substitute.presentation.onboarding.model_onboarding_coordinator import (
    ModelOnboardingCoordinator,
)
from substitute.presentation.onboarding.model_onboarding_session import (
    ModelOnboardingSession,
)
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_existing_model_page import (
    ExistingModelsFolderQuestionPage,
)
from substitute.presentation.onboarding.onboarding_model_download_review_page import (
    ModelDownloadReviewPage,
    download_action_text,
)
from substitute.presentation.onboarding.onboarding_models import OnboardingPageId
from substitute.presentation.onboarding.onboarding_folder_setup_page import (
    FolderSetupPage,
)
from substitute.presentation.onboarding.onboarding_recommendation_pages import (
    ModelRecommendationPage,
)


class ModelOnboardingPresenter:
    """Drive model-page state and generation-safe asynchronous transitions."""

    def __init__(
        self,
        *,
        controller: OnboardingController,
        session: ModelOnboardingSession,
        coordinator: ModelOnboardingCoordinator | None,
        existing_folder_page: ExistingModelsFolderQuestionPage,
        folder_page: FolderSetupPage,
        recommendation_page: ModelRecommendationPage,
        review_page: ModelDownloadReviewPage,
        primary_button: LocalizedPrimaryPushButton,
        navigate: Callable[[OnboardingPageId], None],
        refresh_height: Callable[[], None],
        open_model_page: Callable[[str], object] | None = None,
        recipe_planner: ModelInstallRecipePlanner | None = None,
    ) -> None:
        """Bind focused pages to model state and asynchronous work."""

        self._controller = controller
        self._session = session
        self._coordinator = coordinator
        self._existing_folder_page = existing_folder_page
        self._folder_page = folder_page
        self._recommendation_page = recommendation_page
        self._review_page = review_page
        self._primary_button = primary_button
        self._navigate = navigate
        self._refresh_height = refresh_height
        self._open_model_page = open_model_page or (lambda _url: None)
        self._recipe_planner = recipe_planner or ModelInstallRecipePlanner()
        self._waiting_for_scan = False
        self._waiting_for_recommendations = False
        self._recommendation_failed = False
        self._pending_import_urls: tuple[str, ...] = ()
        folder_page.managed_model_root_edit.textChanged.connect(
            self._model_root_text_changed
        )
        recommendation_page.selection_changed.connect(self._set_version_selected)
        recommendation_page.link_requested.connect(self._open_model_page)
        recommendation_page.own_model_changed.connect(self._set_use_own_model)
        recommendation_page.model_links_requested.connect(self._resolve_model_links)
        recommendation_page.imported_models_accepted.connect(
            self._accept_imported_models
        )
        review_page.remove_requested.connect(self._remove_review_model)
        if coordinator is not None:
            coordinator.scan_finished.connect(self._scan_finished)
            coordinator.recommendation_finished.connect(self._recommendations_finished)
            coordinator.thumbnail_finished.connect(self._thumbnail_finished)
            coordinator.thumbnail_failed.connect(self._thumbnail_failed)
            coordinator.link_import_finished.connect(self._link_import_finished)
            coordinator.task_failed.connect(self._task_failed)

    @property
    def _enabled(self) -> bool:
        """Return whether the current target presents local model onboarding."""

        return self._session.enabled

    def prepare_page(self, page_id: OnboardingPageId) -> None:
        """Project current model state whenever a model page becomes visible."""

        if not self._enabled:
            return
        if page_id is OnboardingPageId.EXISTING_MODELS:
            return
        elif page_id is OnboardingPageId.FOLDERS:
            self._folder_page.configure_model_picker(allow_default=True)
            self._folder_page.reset_scan_status()
            self._refresh_height()
            self._primary_button.setEnabled(True)
        elif page_id is OnboardingPageId.MODEL_RECOMMENDATIONS:
            self._render_current_recommendations()
        elif page_id is OnboardingPageId.MODEL_DOWNLOAD_REVIEW:
            self._render_review()

    def advance(self, page_id: OnboardingPageId) -> bool:
        """Handle model-owned next actions and report whether navigation was consumed."""

        if page_id is OnboardingPageId.EXISTING_MODELS:
            return True
        if page_id is OnboardingPageId.FOLDERS:
            if not self._enabled:
                return False
            return self._advance_folders()
        if page_id is OnboardingPageId.MODEL_RECOMMENDATIONS:
            if self._waiting_for_recommendations:
                return True
            if self._recommendation_failed:
                self._load_recommendations(self._session.state.missing_families)
                return True
            if not (
                self._session.current_family_has_selection()
                or self._session.current_family_is_declined()
            ):
                return True
            self._advance_recommendation_page()
            return True
        if page_id is OnboardingPageId.MODEL_DOWNLOAD_REVIEW:
            self._navigate(OnboardingPageId.INTEGRATIONS)
            return True
        return False

    def go_back(self, page_id: OnboardingPageId) -> bool:
        """Move within paged recommendations while preserving selections."""

        if page_id is OnboardingPageId.MODEL_RECOMMENDATIONS:
            if self._waiting_for_recommendations:
                self._waiting_for_recommendations = False
                if self._coordinator is not None:
                    self._coordinator.cancel()
            self._recommendation_failed = False
            index = self._session.state.recommendation_page_index
            if index > 0:
                self._session.set_page_index(index - 1)
                self._render_current_recommendations()
                return True
        return False

    def confirm_existing_folder_path(self, selected: bool) -> None:
        """Keep the optional external-library choice from blocking continuation."""

        if self._session.state.has_existing_folder is True:
            self._primary_button.setEnabled(True)
        _ = selected

    def _advance_folders(self) -> bool:
        """Scan a chosen folder or request every supported family after No."""

        answer = self._session.state.has_existing_folder
        if answer is None:
            return True
        if not answer:
            self._start_recommendations(frozenset())
            return True
        root = self._controller.draft.managed_model_root
        coordinator = self._coordinator
        if root is None:
            self._start_recommendations(frozenset())
            return True
        if coordinator is None:
            self._show_folder_failure(
                app_text("Choose an accessible existing models folder.")
            )
            return True
        self._waiting_for_scan = True
        self._folder_page.set_scan_status(app_text("Scanning for SDXL and Anima…"))
        apply_application_text(self._primary_button, app_text("Scanning…"))
        self._primary_button.setEnabled(False)
        coordinator.start_scan(root)
        return True

    def choose_existing_folder(self, answer: bool) -> None:
        """Commit one direct folder branch and advance immediately."""

        self._session.answer_existing_folder(answer)
        if not answer:
            self._controller.update_folder_preferences(
                managed_model_root=self._controller.draft.managed_model_root,
                managed_model_root_uses_default=(
                    self._controller.draft.managed_model_root_uses_default
                ),
                output_root=self._controller.draft.output_root,
                output_root_uses_default=self._controller.draft.output_root_uses_default,
            )
        if self._coordinator is not None:
            self._coordinator.cancel()
        if answer:
            self._navigate(OnboardingPageId.FOLDERS)
        else:
            self._start_recommendations(frozenset())

    def _model_root_text_changed(self, text: str) -> None:
        """Keep the shared models folder editable without gating the page."""

        if self._session.state.has_existing_folder is True:
            self._primary_button.setEnabled(True)
        _ = text

    def _scan_finished(self, _generation: int, result: object) -> None:
        """Recommend exactly the supported families absent from a completed scan."""

        if not self._waiting_for_scan or not isinstance(result, ModelFamilyScanResult):
            return
        self._waiting_for_scan = False
        self._session.accept_scan(result)
        if result.status is ModelFamilyScanStatus.CANCELLED:
            return
        if result.status is not ModelFamilyScanStatus.COMPLETED:
            self._show_folder_failure(
                app_text(
                    "The models folder could not be fully scanned. Try again or choose No."
                )
            )
            return
        self._start_recommendations(result.detected_families)

    def _start_recommendations(
        self, detected_families: frozenset[ModelFamilyId]
    ) -> None:
        """Load CivitAI pages for each supported family the scan did not find."""

        missing_families = self._session.select_missing_families(detected_families)
        if not missing_families:
            self._navigate(OnboardingPageId.INTEGRATIONS)
            return
        if self._session.has_loaded_recommendations():
            self._navigate(OnboardingPageId.MODEL_RECOMMENDATIONS)
            return
        self._navigate(OnboardingPageId.MODEL_RECOMMENDATIONS)
        self._load_recommendations(missing_families)

    def _load_recommendations(
        self,
        missing_families: tuple[ModelFamilyId, ...],
    ) -> None:
        """Show the family page immediately and request its provider results."""

        if not missing_families:
            self._navigate(OnboardingPageId.INTEGRATIONS)
            return
        coordinator = self._coordinator
        if coordinator is None:
            self._show_recommendation_failure(
                app_text("Model recommendations are unavailable in this setup run.")
            )
            return
        self._recommendation_failed = False
        self._waiting_for_recommendations = True
        self._recommendation_page.show_loading(missing_families[0])
        self._refresh_height()
        apply_application_text(
            self._primary_button, app_text("Loading recommendations…")
        )
        self._primary_button.setEnabled(False)
        coordinator.start_recommendations(missing_families)

    def _recommendations_finished(self, _generation: int, pages: object) -> None:
        """Accept exact missing-family pages and show the first family."""

        if not self._waiting_for_recommendations or not isinstance(pages, tuple):
            return
        if any(not isinstance(page, FamilyRecommendationPage) for page in pages):
            self._waiting_for_recommendations = False
            self._show_recommendation_failure(
                app_text("CivitAI returned no usable recommendations.")
            )
            return
        self._waiting_for_recommendations = False
        self._recommendation_failed = False
        typed_pages = tuple(
            page for page in pages if isinstance(page, FamilyRecommendationPage)
        )
        if not typed_pages:
            self._show_recommendation_failure(
                app_text("CivitAI returned no usable recommendations.")
            )
            return
        if not self._session.accept_recommendations(typed_pages):
            self._show_recommendation_failure(
                app_text("CivitAI returned no usable recommendations.")
            )
            return
        self._navigate(OnboardingPageId.MODEL_RECOMMENDATIONS)

    def _task_failed(self, _generation: int, operation: str, error: object) -> None:
        """Make scan/provider failure recoverable without stopping background setup."""

        if operation == "scan" and self._waiting_for_scan:
            self._waiting_for_scan = False
            self._show_folder_failure(
                app_text(
                    "The models folder could not be scanned. Try again or choose No."
                )
            )
        elif operation == "recommendations" and self._waiting_for_recommendations:
            self._waiting_for_recommendations = False
            self._show_recommendation_failure(
                app_text(
                    "CivitAI recommendations could not be loaded. Try again or go back."
                )
            )
        elif operation == "link_import" and self._pending_import_urls:
            self._recommendation_page.show_import_results(
                tuple(
                    RecommendationLinkResult(
                        url,
                        RecommendationLinkStatus.UNAVAILABLE,
                    )
                    for url in self._pending_import_urls
                )
            )
            self._pending_import_urls = ()
        _ = error

    def _show_recommendation_failure(self, message: ApplicationText) -> None:
        """Keep provider recovery visible on the recommendation page itself."""

        missing_families = self._session.state.missing_families
        if not missing_families:
            self._show_folder_failure(message)
            return
        self._recommendation_failed = True
        self._recommendation_page.show_failure(missing_families[0], message)
        apply_application_text(self._primary_button, app_text("Try again"))
        self._primary_button.setEnabled(True)
        self._refresh_height()

    def _thumbnail_finished(
        self,
        _generation: int,
        version_id: int,
        result: object,
    ) -> None:
        """Project one independently loaded thumbnail into current session state."""

        if not isinstance(result, ThumbnailAsset):
            return
        if not self._session.accept_thumbnail(version_id, result):
            return
        self._recommendation_page.set_thumbnail(version_id, result)

    def _thumbnail_failed(self, _generation: int, version_id: int) -> None:
        """Settle one failed image without blocking recommendation choices."""

        if not self._session.mark_thumbnail_failed(version_id):
            return
        self._recommendation_page.set_thumbnail_unavailable(version_id)

    def _show_folder_failure(self, message: ApplicationText) -> None:
        """Restore the folder action and show concise retry guidance."""

        self._folder_page.set_scan_status(message)
        apply_application_text(self._primary_button, app_text("Try again"))
        self._primary_button.setEnabled(True)
        self._refresh_height()

    def _set_use_own_model(self, selected: bool) -> None:
        """Store the explicit no-download choice and keep it exclusive with cards."""

        self._session.set_current_family_declined(selected)
        if selected:
            self._recommendation_page.clear_model_selections()
        self._primary_button.setEnabled(
            self._session.current_family_has_selection()
            or self._session.current_family_is_declined()
        )

    def _resolve_model_links(
        self,
        family_id: object,
        urls: tuple[str, ...],
    ) -> None:
        """Validate explicit CivitAI links through the generation-safe coordinator."""

        if not isinstance(family_id, ModelFamilyId):
            return
        coordinator = self._coordinator
        if coordinator is None:
            self._recommendation_page.show_import_results(
                tuple(
                    RecommendationLinkResult(url, RecommendationLinkStatus.UNAVAILABLE)
                    for url in urls
                )
            )
            return
        self._pending_import_urls = urls
        coordinator.start_link_import(
            family_id,
            urls,
            excluded_version_ids=frozenset(
                card.recommendation.version_id
                for page in self._session.state.recommendation_pages
                for card in page.cards
            ),
        )

    def _link_import_finished(self, _generation: int, result: object) -> None:
        """Show typed link results without changing selections until acceptance."""

        if not isinstance(result, tuple) or any(
            not isinstance(item, RecommendationLinkResult) for item in result
        ):
            return
        self._pending_import_urls = ()
        self._recommendation_page.show_import_results(result)

    def _accept_imported_models(
        self,
        cards: tuple[RecommendationCardAsset, ...],
    ) -> None:
        """Commit validated imports to session state and the editable checkout."""

        if self._session.replace_current_family_imports(cards):
            self._recommendation_page.clear_own_model_choice()
            self._render_current_recommendations()

    def _advance_recommendation_page(self) -> None:
        """Advance to the next missing family or finish recommendation selection."""

        state = self._session.state
        next_index = state.recommendation_page_index + 1
        if next_index < len(state.recommendation_pages):
            self._session.set_page_index(next_index)
            self._render_current_recommendations()
            return
        self._finish_recommendations()

    def _finish_recommendations(self) -> None:
        """Route selected files through review and empty choices to integrations."""

        if self._session.state.selected_version_ids:
            self._navigate(OnboardingPageId.MODEL_DOWNLOAD_REVIEW)
        else:
            self._navigate(OnboardingPageId.INTEGRATIONS)

    def _render_current_recommendations(self) -> None:
        """Render the current catalog page with retained explicit selections."""

        state = self._session.state
        if not state.recommendation_pages:
            return
        page = state.recommendation_pages[state.recommendation_page_index]
        self._recommendation_page.set_recommendations(
            page,
            selected_version_ids=state.selected_version_ids,
            use_own_model=self._session.current_family_is_declined(),
        )
        self._primary_button.setEnabled(
            self._session.current_family_has_selection()
            or self._session.current_family_is_declined()
        )
        self._refresh_height()

    def _set_version_selected(self, version_id: int, selected: bool) -> None:
        """Retain one exact-version selection and update the Continue gate."""

        if self._session.set_version_selected(version_id, selected):
            if selected:
                self._recommendation_page.clear_own_model_choice()
            self._primary_button.setEnabled(
                self._session.current_family_has_selection()
                or self._session.current_family_is_declined()
            )

    def _render_review(self) -> None:
        """Show exact selected primary models as an editable checkout."""

        selected = self._session.selected_recommendations()
        model_root = self._controller.draft.managed_model_root
        if model_root is None:
            self._show_folder_failure(
                app_text("Choose a models folder before reviewing downloads.")
            )
            return
        plan = self._recipe_planner.plan(selected, model_root=model_root)
        self._session.accept_install_plan(plan)
        self._review_page.set_plan(plan, self._session.selected_cards())
        apply_application_text(
            self._primary_button,
            download_action_text(plan),
        )
        self._primary_button.setEnabled(bool(plan.files) and plan.has_sufficient_space)
        self._refresh_height()

    def _remove_review_model(self, version_id: int) -> None:
        """Remove one checkout item and immediately refresh totals and action state."""

        if self._session.set_version_selected(version_id, False):
            self._render_review()


__all__ = ["ModelOnboardingPresenter"]
