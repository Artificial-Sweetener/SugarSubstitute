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

"""Own mutable first-run model-onboarding selection state."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.model_recommendations import (
    FamilyRecommendationPage,
    RecommendationCardAsset,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import (
    SUPPORTED_MODEL_FAMILIES,
    ModelFamilyId,
    ModelFamilyScanResult,
    ModelInstallPlan,
    ModelRecommendation,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingFlowMode,
    OnboardingModelState,
    OnboardingTargetMode,
)


class ModelOnboardingSession:
    """Own model choices and invalidate derived state when inputs change."""

    def __init__(
        self,
        *,
        flow_mode: OnboardingFlowMode,
        target_mode: OnboardingTargetMode,
    ) -> None:
        """Initialize empty state for one onboarding window session."""

        self._flow_mode = flow_mode
        self._target_mode = target_mode
        self._state = OnboardingModelState()

    @property
    def state(self) -> OnboardingModelState:
        """Return the current immutable model-onboarding state."""

        return self._state

    @property
    def enabled(self) -> bool:
        """Return whether this session owns local first-run model setup."""

        return (
            self._flow_mode is OnboardingFlowMode.FIRST_RUN
            and self._target_mode is not OnboardingTargetMode.REMOTE
        )

    def set_target_mode(self, target_mode: OnboardingTargetMode) -> None:
        """Update target ownership and clear local selections for remote setup."""

        self._target_mode = target_mode
        if target_mode is OnboardingTargetMode.REMOTE:
            self._state = OnboardingModelState()

    def answer_existing_folder(self, answer: bool | None) -> None:
        """Record the explicit existing-folder answer and clear derived state."""

        if answer is self._state.has_existing_folder:
            return
        self._state = replace(
            self._state,
            has_existing_folder=answer,
            scan_result=None,
            missing_families=(),
            recommendation_pages=(),
            recommendation_page_index=0,
            selected_version_ids=frozenset(),
            declined_family_ids=frozenset(),
            install_plan=None,
        )

    def accept_scan(self, result: ModelFamilyScanResult) -> None:
        """Record one typed existing-model scan result."""

        self._state = replace(self._state, scan_result=result)

    def select_missing_families(
        self, detected_families: frozenset[ModelFamilyId]
    ) -> tuple[ModelFamilyId, ...]:
        """Queue unsupported families in catalog order and invalidate stale cards."""

        missing_families = SUPPORTED_MODEL_FAMILIES.missing_from(detected_families)

        if (
            missing_families == self._state.missing_families
            and self._state.recommendation_pages
        ):
            self._state = replace(
                self._state,
                recommendation_page_index=0,
                install_plan=None,
            )
            return missing_families

        self._state = replace(
            self._state,
            missing_families=missing_families,
            recommendation_pages=(),
            recommendation_page_index=0,
            selected_version_ids=frozenset(),
            declined_family_ids=frozenset(),
            install_plan=None,
        )
        return missing_families

    def has_loaded_recommendations(self) -> bool:
        """Return whether this session already owns every requested family page."""

        return (
            bool(self._state.recommendation_pages)
            and tuple(page.family_id for page in self._state.recommendation_pages)
            == self._state.missing_families
        )

    def accept_recommendations(
        self, pages: tuple[FamilyRecommendationPage, ...]
    ) -> bool:
        """Accept pages only when their family order matches the selection."""

        if tuple(page.family_id for page in pages) != self._state.missing_families:
            return False
        self._state = replace(
            self._state,
            recommendation_pages=pages,
            recommendation_page_index=0,
        )
        return True

    def set_page_index(self, index: int) -> None:
        """Select one loaded family page by bounded index."""

        if index < 0 or index >= len(self._state.recommendation_pages):
            raise ValueError("Recommendation page index is outside the loaded pages.")
        self._state = replace(self._state, recommendation_page_index=index)

    def clear_current_family_selection(self) -> None:
        """Discard selections from the family page the user explicitly skipped."""

        if not self._state.recommendation_pages:
            return
        page = self._state.recommendation_pages[self._state.recommendation_page_index]
        current_ids = {card.recommendation.version_id for card in page.all_cards}
        self._state = replace(
            self._state,
            selected_version_ids=self._state.selected_version_ids.difference(
                current_ids
            ),
            install_plan=None,
        )

    def current_family_has_selection(self) -> bool:
        """Return whether the visible family page has an explicit selection."""

        if not self._state.recommendation_pages:
            return False
        page = self._state.recommendation_pages[self._state.recommendation_page_index]
        return any(
            card.recommendation.version_id in self._state.selected_version_ids
            for card in page.all_cards
        )

    def current_family_is_declined(self) -> bool:
        """Return whether the user chose to provide the visible family themselves."""

        if not self._state.recommendation_pages:
            return False
        family_id = self._state.recommendation_pages[
            self._state.recommendation_page_index
        ].family_id
        return family_id in self._state.declined_family_ids

    def set_current_family_declined(self, declined: bool) -> None:
        """Store one explicit no-download choice for the visible model family."""

        if not self._state.recommendation_pages:
            return
        page = self._state.recommendation_pages[self._state.recommendation_page_index]
        declined_family_ids = set(self._state.declined_family_ids)
        if declined:
            declined_family_ids.add(page.family_id)
            current_ids = {card.recommendation.version_id for card in page.all_cards}
            selected_version_ids = self._state.selected_version_ids.difference(
                current_ids
            )
        else:
            declined_family_ids.discard(page.family_id)
            selected_version_ids = self._state.selected_version_ids
        self._state = replace(
            self._state,
            declined_family_ids=frozenset(declined_family_ids),
            selected_version_ids=selected_version_ids,
            install_plan=None,
        )

    def set_version_selected(self, version_id: int, selected: bool) -> bool:
        """Retain one exact-version selection and reject stale card signals."""

        available_ids = {
            card.recommendation.version_id
            for page in self._state.recommendation_pages
            for card in page.all_cards
        }
        if version_id not in available_ids:
            return False

        selected_ids = set(self._state.selected_version_ids)
        if selected:
            selected_ids.add(version_id)
            selected_family_ids = {
                page.family_id
                for page in self._state.recommendation_pages
                if any(
                    card.recommendation.version_id == version_id
                    for card in page.all_cards
                )
            }
            declined_family_ids = self._state.declined_family_ids.difference(
                selected_family_ids
            )
        else:
            selected_ids.discard(version_id)
            declined_family_ids = self._state.declined_family_ids
        self._state = replace(
            self._state,
            selected_version_ids=frozenset(selected_ids),
            declined_family_ids=declined_family_ids,
            install_plan=None,
        )
        return True

    def replace_current_family_imports(
        self,
        cards: tuple[RecommendationCardAsset, ...],
    ) -> bool:
        """Replace one family's imported cards and select every accepted model."""

        if not self._state.recommendation_pages:
            return False
        page_index = self._state.recommendation_page_index
        page = self._state.recommendation_pages[page_index]
        curated_ids = {card.recommendation.version_id for card in page.cards}
        imported_ids = {card.recommendation.version_id for card in cards}
        if curated_ids.intersection(imported_ids):
            return False
        pages = list(self._state.recommendation_pages)
        pages[page_index] = replace(page, imported_cards=cards)
        previous_import_ids = {
            card.recommendation.version_id for card in page.imported_cards
        }
        selected_ids = self._state.selected_version_ids.difference(
            previous_import_ids
        ).union(imported_ids)
        declined = self._state.declined_family_ids.difference({page.family_id})
        self._state = replace(
            self._state,
            recommendation_pages=tuple(pages),
            selected_version_ids=frozenset(selected_ids),
            declined_family_ids=declined,
            install_plan=None,
        )
        return True

    def accept_thumbnail(self, version_id: int, thumbnail: ThumbnailAsset) -> bool:
        """Attach one asynchronously loaded image to its exact version."""

        return self._replace_thumbnail_state(
            version_id,
            thumbnail=thumbnail,
            thumbnail_failed=False,
        )

    def mark_thumbnail_failed(self, version_id: int) -> bool:
        """Stop the busy state for one exact version whose image failed."""

        return self._replace_thumbnail_state(
            version_id,
            thumbnail=None,
            thumbnail_failed=True,
        )

    def accept_install_plan(self, plan: ModelInstallPlan) -> None:
        """Record the exact reviewed files that gate final setup."""

        self._state = replace(self._state, install_plan=plan)

    def selected_recommendations(self) -> tuple[ModelRecommendation, ...]:
        """Return selected recommendations in family and provider order."""

        selected_ids = self._state.selected_version_ids
        return tuple(
            card.recommendation
            for page in self._state.recommendation_pages
            for card in page.all_cards
            if card.recommendation.version_id in selected_ids
        )

    def selected_cards(self) -> tuple[RecommendationCardAsset, ...]:
        """Return selected cards with their exact retained thumbnail payloads."""

        selected_ids = self._state.selected_version_ids
        return tuple(
            card
            for page in self._state.recommendation_pages
            for card in page.all_cards
            if card.recommendation.version_id in selected_ids
        )

    def _replace_thumbnail_state(
        self,
        version_id: int,
        *,
        thumbnail: ThumbnailAsset | None,
        thumbnail_failed: bool,
    ) -> bool:
        """Replace one card image state while retaining every user selection."""

        found = False
        pages: list[FamilyRecommendationPage] = []
        for page in self._state.recommendation_pages:
            cards = []
            for card in page.all_cards:
                if card.recommendation.version_id == version_id:
                    card = replace(
                        card,
                        thumbnail=thumbnail,
                        thumbnail_failed=thumbnail_failed,
                    )
                    found = True
                cards.append(card)
            curated_count = len(page.cards)
            pages.append(
                replace(
                    page,
                    cards=tuple(cards[:curated_count]),
                    imported_cards=tuple(cards[curated_count:]),
                )
            )
        if found:
            self._state = replace(self._state, recommendation_pages=tuple(pages))
        return found


__all__ = ["ModelOnboardingSession"]
