from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from django.core.cache import cache
from django.db import transaction
from web_project.settings.config import TIMING

from ..models import Boulder, Participant, Result

logger = logging.getLogger(__name__)


@dataclass
class SubmittedResult:
    zone1: bool
    zone2: bool
    top: bool
    attempts_zone1: int
    attempts_zone2: int
    attempts_top: int
    version: int | None = None


class ResultService:
    @staticmethod
    def extract_from_post(post_data, boulder_id: int) -> SubmittedResult:
        """
        Extract submitted result data from POST data using ResultSubmissionForm.

        Args:
            post_data: POST data dict (request.POST)
            boulder_id: ID of the boulder

        Returns:
            SubmittedResult dataclass with validated data
        """
        from ..forms import ResultSubmissionForm

        # Extract boulder-specific fields from POST data
        form_data = {
            'zone1': post_data.get(f"zone1_{boulder_id}"),
            'zone2': post_data.get(f"zone2_{boulder_id}"),
            'top': post_data.get(f"sent_{boulder_id}"),
            'attempts_zone1': post_data.get(f"attempts_zone1_{boulder_id}"),
            'attempts_zone2': post_data.get(f"attempts_zone2_{boulder_id}"),
            'attempts_top': post_data.get(f"attempts_top_{boulder_id}"),
            'version': post_data.get(f"ver_{boulder_id}"),
        }

        form = ResultSubmissionForm(boulder_id=boulder_id, data=form_data)

        # Form validation is lenient - it will clean invalid data rather than rejecting it
        if form.is_valid():
            return form.get_submitted_result()

        # Fallback to safe defaults if form is invalid (shouldn't happen with current validation)
        logger.warning(f"ResultSubmissionForm validation failed for boulder {boulder_id}: {form.errors}")
        return SubmittedResult(
            zone1=False,
            zone2=False,
            top=False,
            attempts_zone1=0,
            attempts_zone2=0,
            attempts_top=0,
            version=None,
        )
    
    @staticmethod
    def normalize_submission(boulder: Boulder, submission: SubmittedResult) -> SubmittedResult:
        """
        Enforce zone hierarchy and attempt defaults for a submitted result.
        
        Rules:
        - No zones: zone1=False, zone2=False
        - One zone: zone2=False, top implies zone1
        - Two zones: top implies zone2 and zone1, zone2 implies zone1
        """
        if boulder.zone_count == 0:
            return ResultService._normalize_no_zones(submission)
        
        if boulder.zone_count == 1:
            return ResultService._normalize_single_zone(submission)
        
        return ResultService._normalize_two_zones(submission, boulder)
    
    @staticmethod
    def _normalize_no_zones(submission: SubmittedResult) -> SubmittedResult:
        """Normalize submission for boulder with no zones."""
        attempts_top = max(submission.attempts_top, 0)
        if submission.top and attempts_top < 1:
            attempts_top = 1

        return SubmittedResult(
            zone1=False,
            zone2=False,
            top=submission.top,
            attempts_zone1=0,
            attempts_zone2=0,
            attempts_top=attempts_top,
            version=submission.version,
        )
    
    @staticmethod
    def _normalize_single_zone(submission: SubmittedResult) -> SubmittedResult:
        """Normalize submission for boulder with one zone."""
        zone1 = submission.zone1
        top = submission.top

        if top:
            zone1 = True
        if not zone1:
            top = False

        attempts_z1 = max(submission.attempts_zone1, 0)
        attempts_top = max(submission.attempts_top, 0)

        if zone1 and attempts_z1 < 1:
            attempts_z1 = 1
        if top and attempts_top < 1:
            attempts_top = 1
        if top and attempts_top and attempts_z1 == 0:
            attempts_z1 = attempts_top
        if top and attempts_top and attempts_top < attempts_z1:
            attempts_top = attempts_z1

        return SubmittedResult(
            zone1=zone1,
            zone2=False,
            top=top,
            attempts_zone1=attempts_z1,
            attempts_zone2=0,
            attempts_top=attempts_top,
            version=submission.version,
        )
    
    @staticmethod
    def _normalize_two_zones(submission: SubmittedResult, boulder: Boulder) -> SubmittedResult:
        """Normalize submission for boulder with two zones."""
        zone1 = submission.zone1
        zone2 = submission.zone2
        top = submission.top

        if top:
            zone2 = True
            zone1 = True
        if zone2 and not zone1:
            zone1 = True
        if not zone1:
            zone2 = False
            top = False

        attempts_z1 = max(submission.attempts_zone1, 0)
        attempts_z2 = max(submission.attempts_zone2, 0)
        attempts_top = max(submission.attempts_top, 0)

        if zone1 and attempts_z1 < 1:
            attempts_z1 = 1
        if zone2 and attempts_z2 < 1:
            attempts_z2 = 1
        if top and attempts_top < 1:
            attempts_top = 1

        if top and attempts_top and attempts_z2 == 0:
            attempts_z2 = attempts_top
        if top and attempts_top and attempts_z1 == 0:
            attempts_z1 = attempts_top
        if zone2 and attempts_z2 and attempts_z1 == 0:
            attempts_z1 = attempts_z2

        if zone2 and attempts_z2 and attempts_z2 < attempts_z1:
            attempts_z2 = attempts_z1
        if top and attempts_top:
            baseline = attempts_z2 if zone2 else attempts_z1
            if attempts_top < baseline:
                attempts_top = baseline

        return SubmittedResult(
            zone1=zone1,
            zone2=zone2,
            top=top,
            attempts_zone1=attempts_z1,
            attempts_zone2=attempts_z2,
            attempts_top=attempts_top,
            version=submission.version,
        )
    
    @staticmethod
    def result_to_payload(result: Result) -> dict:
        """Convert Result model to JSON payload."""
        return {
            "top": result.top,
            "zone2": result.zone2,
            "zone1": result.zone1,
            "attempts_top": result.attempts_top,
            "attempts_zone2": result.attempts_zone2,
            "attempts_zone1": result.attempts_zone1,
            "version": result.version,
            "updated_at": result.updated_at.timestamp(),  # Keep for backward compatibility
        }
    
    @staticmethod
    def load_existing_results(participant: Participant, boulders: Iterable[Boulder]) -> dict[int, Result]:
        """Load existing results for participant and boulders."""
        return {
            res.boulder_id: res
            for res in Result.objects.filter(participant=participant, boulder__in=boulders)
        }
    
    @staticmethod
    def handle_submission(
        post_data, participant: Participant, boulders: Iterable[Boulder]
    ) -> dict[int, dict]:
        """
        Handle result submission from POST data.
        
        Returns dict mapping boulder_id to result payload.
        Invalidates scoreboard cache on success.
        """
        payload: dict[int, dict] = {}
        
        with transaction.atomic():
            for boulder in boulders:
                submission = ResultService.normalize_submission(
                    boulder, 
                    ResultService.extract_from_post(post_data, boulder.id)
                )
                
                current_result = (
                    Result.objects.select_for_update()
                    .filter(participant=participant, boulder=boulder)
                    .first()
                )

                # Version-based optimistic locking conflict detection
                if current_result and submission.version is not None:
                    if current_result.version != submission.version:
                        # Version mismatch: someone else modified this result
                        # Return current server state to client
                        logger.info(
                            f"Version conflict detected for result {current_result.id}: "
                            f"client version={submission.version}, server version={current_result.version}. "
                            f"Rejecting update."
                        )
                        payload[boulder.id] = ResultService.result_to_payload(current_result)
                        continue

                if not current_result:
                    current_result = Result(participant=participant, boulder=boulder)
                
                current_result.zone1 = submission.zone1
                current_result.zone2 = submission.zone2
                current_result.top = submission.top
                current_result.attempts_zone1 = submission.attempts_zone1
                current_result.attempts_zone2 = submission.attempts_zone2
                current_result.attempts_top = submission.attempts_top
                current_result.attempts = (
                    submission.attempts_top
                    if submission.top
                    else (submission.attempts_zone2 if submission.zone2 else submission.attempts_zone1)
                )
                current_result.save()
                payload[boulder.id] = ResultService.result_to_payload(current_result)
        
        # Invalidate scoreboard cache for this participant's age group
        if participant.age_group_id:
            for grading in ["ifsc", "point_based"]:
                cache.delete(f"scoreboard_{participant.age_group_id}_{grading}")
                cache.delete(f"scoreboard_all_{grading}")
        
        return payload
