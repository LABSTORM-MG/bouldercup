from __future__ import annotations

import logging
from typing import Iterable, Mapping, Sequence

from django.core.cache import cache
from web_project.settings.config import TIMING

from ..models import CompetitionSettings, Participant, Result

logger = logging.getLogger(__name__)


class ScoringService:
    # Grading systems that use points
    POINT_BASED_SYSTEMS = {"point_based", "point_based_dynamic", "point_based_dynamic_attempts"}
    # Dynamic grading systems (percentage-based top points)
    DYNAMIC_SYSTEMS = {"point_based_dynamic", "point_based_dynamic_attempts"}

    @staticmethod
    def get_active_settings() -> CompetitionSettings | None:
        """Get active competition settings with caching."""
        cached = cache.get('competition_settings')
        if cached is None:
            cached = CompetitionSettings.objects.order_by("-updated_at", "-id").first()
            if cached:
                cache.set('competition_settings', cached, TIMING.SETTINGS_CACHE_TIMEOUT)
                logger.debug("Competition settings cached")
        return cached

    @staticmethod
    def invalidate_settings_cache() -> None:
        """Invalidate cached competition settings."""
        cache.delete('competition_settings')
        logger.info("Competition settings cache invalidated")
    
    @staticmethod
    def score_ifsc(results: Iterable[Result]) -> dict:
        """
        Aggregate IFSC-style scoring metrics for a set of results.
        
        Returns:
            Dict with keys: tops, zones, top_attempts, zone_attempts
        """
        tops = zones = top_attempts = zone_attempts = 0
        for res in results:
            if res.top:
                tops += 1
                top_attempts += res.attempts_top or res.attempts
            if res.zone2 or res.zone1:
                zones += 1
                if res.zone2:
                    zone_attempts += res.attempts_zone2 or res.attempts
                elif res.zone1:
                    zone_attempts += res.attempts_zone1 or res.attempts
        return {
            "tops": tops,
            "zones": zones,
            "top_attempts": top_attempts,
            "zone_attempts": zone_attempts,
        }
    
    @staticmethod
    def score_point_based(results: Iterable[Result], settings: CompetitionSettings) -> dict:
        """
        Compute points for point-based scoring.
        
        Returns:
            Dict with keys: points, tops, zones, attempts
        """
        points = 0
        tops = zones = total_attempts = 0
        
        for res in results:
            achieved_zone = res.zone2 or res.zone1
            
            if res.top:
                attempts_used = res.attempts_top or res.attempts
                tops += 1
                base = settings.flash_points if attempts_used == 1 else settings.top_points
                penalty = settings.attempt_penalty * max(attempts_used - 1, 0)
                pts = max(base - penalty, settings.min_top_points)
                points += pts
                total_attempts += attempts_used
            elif achieved_zone:
                attempts_used = res.attempts_zone2 if res.zone2 else res.attempts_zone1 or res.attempts
                zones += 1
                is_two_zone = getattr(res.boulder, "zone_count", 0) >= 2
                
                if res.zone2:
                    base = settings.zone2_points
                    min_zone = settings.min_zone2_points
                elif is_two_zone:
                    base = settings.zone1_points
                    min_zone = settings.min_zone1_points
                else:
                    base = settings.zone_points
                    min_zone = settings.min_zone_points
                
                penalty = settings.attempt_penalty * max(attempts_used - 1, 0)
                pts = max(base - penalty, min_zone)
                points += pts
                total_attempts += attempts_used
            else:
                total_attempts += res.attempts
        
        return {
            "points": points,
            "tops": tops,
            "zones": zones,
            "attempts": total_attempts,
        }

    @staticmethod
    def get_dynamic_top_points(settings: CompetitionSettings, top_percentage: float) -> int:
        """
        Get top points based on percentage of participants who topped the boulder.

        Args:
            settings: Competition settings with percentage tier values
            top_percentage: Percentage of participants who topped (0-100)

        Returns:
            Points for the top based on the percentage tier
        """
        if top_percentage > 90:
            return settings.top_points_100
        elif top_percentage > 80:
            return settings.top_points_90
        elif top_percentage > 70:
            return settings.top_points_80
        elif top_percentage > 60:
            return settings.top_points_70
        elif top_percentage > 50:
            return settings.top_points_60
        elif top_percentage > 40:
            return settings.top_points_50
        elif top_percentage > 30:
            return settings.top_points_40
        elif top_percentage > 20:
            return settings.top_points_30
        elif top_percentage > 10:
            return settings.top_points_20
        else:
            return settings.top_points_10

    @staticmethod
    def count_tops_per_boulder(results: Iterable[Result]) -> dict[int, int]:
        """
        Count how many participants topped each boulder.

        Args:
            results: All results to analyze

        Returns:
            Dict mapping boulder_id to number of tops
        """
        top_counts: dict[int, int] = {}
        for res in results:
            if res.top:
                top_counts[res.boulder_id] = top_counts.get(res.boulder_id, 0) + 1
        return top_counts

    @staticmethod
    def score_point_based_dynamic(
        results: Iterable[Result],
        settings: CompetitionSettings,
        top_counts: Mapping[int, int],
        participant_count: int,
    ) -> dict:
        """
        Compute points for dynamic point-based scoring.

        Top points are based on the percentage of participants who topped each boulder.
        No attempt penalty for tops.
        Zone scoring follows standard point-based rules (with attempt penalty).

        Args:
            results: Results for a single participant
            settings: Competition settings
            top_counts: Dict mapping boulder_id to number of tops
            participant_count: Total number of participants in the category

        Returns:
            Dict with keys: points, tops, zones, attempts
        """
        points = 0
        tops = zones = total_attempts = 0

        for res in results:
            achieved_zone = res.zone2 or res.zone1

            if res.top:
                attempts_used = res.attempts_top or res.attempts
                tops += 1

                # Flash (first attempt) gets flash points, otherwise use percentage-based points
                if attempts_used == 1:
                    pts = settings.flash_points
                else:
                    # Calculate percentage of participants who topped this boulder
                    boulder_tops = top_counts.get(res.boulder_id, 0)
                    top_percentage = (boulder_tops / participant_count * 100) if participant_count > 0 else 0
                    # Get points based on percentage tier (no attempt penalty for tops)
                    pts = ScoringService.get_dynamic_top_points(settings, top_percentage)

                points += pts
                total_attempts += attempts_used
            elif achieved_zone:
                zones += 1
                is_two_zone = getattr(res.boulder, "zone_count", 0) >= 2

                # Zone points without attempt penalty in dynamic mode
                if res.zone2:
                    pts = settings.zone2_points
                elif is_two_zone:
                    pts = settings.zone1_points
                else:
                    pts = settings.zone_points

                points += pts
                total_attempts += res.attempts_zone2 if res.zone2 else res.attempts_zone1 or res.attempts
            else:
                total_attempts += res.attempts

        return {
            "points": points,
            "tops": tops,
            "zones": zones,
            "attempts": total_attempts,
        }

    @staticmethod
    def score_point_based_dynamic_attempts(
        results: Iterable[Result],
        settings: CompetitionSettings,
        top_counts: Mapping[int, int],
        participant_count: int,
    ) -> dict:
        """
        Compute points for dynamic point-based scoring with attempt penalties.

        Like score_point_based_dynamic but with attempt penalties for tops and zones.

        Args:
            results: Results for a single participant
            settings: Competition settings
            top_counts: Dict mapping boulder_id to number of tops
            participant_count: Total number of participants in the category

        Returns:
            Dict with keys: points, tops, zones, attempts
        """
        points = 0
        tops = zones = total_attempts = 0

        for res in results:
            achieved_zone = res.zone2 or res.zone1

            if res.top:
                attempts_used = res.attempts_top or res.attempts
                tops += 1

                # Flash (first attempt) gets flash points
                if attempts_used == 1:
                    pts = settings.flash_points
                else:
                    # Calculate percentage of participants who topped this boulder
                    boulder_tops = top_counts.get(res.boulder_id, 0)
                    top_percentage = (boulder_tops / participant_count * 100) if participant_count > 0 else 0
                    # Get points based on percentage tier, then apply attempt penalty
                    base = ScoringService.get_dynamic_top_points(settings, top_percentage)
                    penalty = settings.attempt_penalty * max(attempts_used - 1, 0)
                    pts = max(base - penalty, settings.min_top_points)

                points += pts
                total_attempts += attempts_used
            elif achieved_zone:
                attempts_used = res.attempts_zone2 if res.zone2 else res.attempts_zone1 or res.attempts
                zones += 1
                is_two_zone = getattr(res.boulder, "zone_count", 0) >= 2

                # Zone points with attempt penalty and min points
                if res.zone2:
                    base = settings.zone2_points
                    min_zone = settings.min_zone2_points
                elif is_two_zone:
                    base = settings.zone1_points
                    min_zone = settings.min_zone1_points
                else:
                    base = settings.zone_points
                    min_zone = settings.min_zone_points

                penalty = settings.attempt_penalty * max(attempts_used - 1, 0)
                pts = max(base - penalty, min_zone)
                points += pts
                total_attempts += attempts_used
            else:
                total_attempts += res.attempts

        return {
            "points": points,
            "tops": tops,
            "zones": zones,
            "attempts": total_attempts,
        }

    @staticmethod
    def rank_entries(entries: list[dict], grading_system: str = "ifsc") -> None:
        """
        Assign ranks to scoreboard entries based on grading system.

        Modifies entries in-place by adding a 'rank' key to each entry.
        Handles ties by assigning the same rank to entries with identical scores.

        Args:
            entries: List of dicts with participant and scoring data
            grading_system: 'ifsc', 'point_based', or 'point_based_dynamic'
        """
        def sort_key(entry: dict):
            if grading_system in ScoringService.POINT_BASED_SYSTEMS:
                return (
                    -entry.get("points", 0),
                    -entry.get("tops", 0),
                    -entry.get("zones", 0),
                    entry.get("attempts", 0),
                    entry["participant"].name.lower(),
                )

            top_att = entry.get("top_attempts", 0) if entry.get("tops", 0) > 0 else float("inf")
            zone_att = entry.get("zone_attempts", 0) if entry.get("zones", 0) > 0 else float("inf")
            return (
                -entry.get("tops", 0),
                -entry.get("zones", 0),
                top_att,
                zone_att,
                entry["participant"].name.lower(),
            )
        
        entries.sort(key=sort_key)
        last_key = None
        current_rank = 0
        
        for idx, entry in enumerate(entries, start=1):
            key = sort_key(entry)
            if key != last_key:
                current_rank = idx
                last_key = key
            entry["rank"] = current_rank
    
    @staticmethod
    def group_results_by_participant(results: Iterable[Result]) -> dict[int, list[Result]]:
        """Group results by participant ID."""
        result_map: dict[int, list[Result]] = {}
        for res in results:
            result_map.setdefault(res.participant_id, []).append(res)
        return result_map
    
    @staticmethod
    def build_scoreboard_entries(
        participants: Sequence[Participant],
        result_map: Mapping[int, Sequence[Result]],
        grading_system: str,
        settings: CompetitionSettings | None,
        top_counts: Mapping[int, int] | None = None,
        participant_count: int | None = None,
    ) -> list[dict]:
        """
        Build scoreboard entries for participants.

        Args:
            participants: List of participants to score
            result_map: Dict mapping participant_id to their results
            grading_system: 'ifsc', 'point_based', or 'point_based_dynamic'
            settings: Competition settings
            top_counts: For dynamic scoring - dict mapping boulder_id to number of tops
            participant_count: For dynamic scoring - total number of participants

        Returns:
            List of dicts with participant data and scores, sorted by rank
        """
        entries: list[dict] = []

        for participant in participants:
            res_list = list(result_map.get(participant.id, ()))

            if grading_system == "point_based_dynamic_attempts" and settings and top_counts is not None:
                scored = ScoringService.score_point_based_dynamic_attempts(
                    res_list, settings, top_counts, participant_count or len(participants)
                )
            elif grading_system == "point_based_dynamic" and settings and top_counts is not None:
                scored = ScoringService.score_point_based_dynamic(
                    res_list, settings, top_counts, participant_count or len(participants)
                )
            elif grading_system == "point_based" and settings:
                scored = ScoringService.score_point_based(res_list, settings)
            else:
                scored = ScoringService.score_ifsc(res_list)

            entries.append(
                {
                    "participant": participant,
                    **scored,
                }
            )

        ScoringService.rank_entries(entries, grading_system)
        return entries
    
    @staticmethod
    def get_cached_scoreboard(age_group_id: int | str, grading_system: str) -> dict | None:
        """Get cached scoreboard data if available."""
        cache_key = f"scoreboard_{age_group_id}_{grading_system}"
        return cache.get(cache_key)
    
    @staticmethod
    def cache_scoreboard(age_group_id: int | str, grading_system: str, data: dict) -> None:
        """Cache scoreboard data."""
        cache_key = f"scoreboard_{age_group_id}_{grading_system}"
        cache.set(cache_key, data, timeout=TIMING.SCOREBOARD_CACHE_TIMEOUT)
