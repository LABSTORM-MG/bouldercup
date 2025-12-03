from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from .models import CompetitionSettings, Participant, Result


def score_ifsc(results: Iterable[Result]) -> dict:
    """Aggregate IFSC-style scoring metrics for a set of results."""
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


def score_point_based(results: Iterable[Result], settings: CompetitionSettings) -> dict:
    """Compute points for point-based scoring."""
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


def rank_entries(entries: list[dict], grading_system: str = "ifsc") -> None:
    """Assign ranks based on scoring system (in-place)."""

    def sort_key(entry: dict):
        if grading_system == "point_based":
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


def group_results_by_participant(results: Iterable[Result]) -> dict[int, list[Result]]:
    result_map: dict[int, list[Result]] = {}
    for res in results:
        result_map.setdefault(res.participant_id, []).append(res)
    return result_map


def build_scoreboard_entries(
    participants: Sequence[Participant],
    result_map: Mapping[int, Sequence[Result]],
    grading_system: str,
    settings: CompetitionSettings | None,
) -> list[dict]:
    entries: list[dict] = []
    for participant in participants:
        res_list = list(result_map.get(participant.id, ()))
        if grading_system == "point_based" and settings:
            scored = score_point_based(res_list, settings)
        else:
            scored = score_ifsc(res_list)
        entries.append(
            {
                "participant": participant,
                **scored,
            }
        )
    rank_entries(entries, grading_system)
    return entries
