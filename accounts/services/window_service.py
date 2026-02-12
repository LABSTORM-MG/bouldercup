"""
Submission window service for managing time-based result submission windows.

This service encapsulates submission window logic, making it reusable and testable.
"""
from dataclasses import dataclass
from typing import Optional

from ..models import AgeGroup, SubmissionWindow


@dataclass
class SubmissionWindowStatus:
    """
    Encapsulates submission window state for a participant's age group.

    Attributes:
        can_submit: Whether result submission is currently allowed
        has_windows: Whether any submission windows are configured for this age group
        active_window: The currently active submission window (if any)
        next_window: The next upcoming submission window (if any)
        active_window_end_timestamp: Unix timestamp when active window ends (for countdown)
        next_window_timestamp: Unix timestamp when next window starts (for countdown)
    """
    can_submit: bool
    has_windows: bool
    active_window: Optional[SubmissionWindow]
    next_window: Optional[SubmissionWindow]
    active_window_end_timestamp: Optional[float]
    next_window_timestamp: Optional[float]


class WindowService:
    """Service for managing submission window logic."""

    @staticmethod
    def get_submission_status(
        age_group: Optional[AgeGroup],
        grace_period_seconds: int = 0
    ) -> SubmissionWindowStatus:
        """
        Get submission window status for an age group.

        Args:
            age_group: The age group to check (None if participant has no age group)
            grace_period_seconds: Optional grace period after window end (default: 0)

        Returns:
            SubmissionWindowStatus with all relevant window information
        """
        if not age_group:
            # No age group = no restrictions, allow submission
            return SubmissionWindowStatus(
                can_submit=True,
                has_windows=False,
                active_window=None,
                next_window=None,
                active_window_end_timestamp=None,
                next_window_timestamp=None,
            )

        # Check submission allowance
        can_submit = SubmissionWindow.is_submission_allowed(
            age_group,
            grace_period_seconds=grace_period_seconds
        )
        has_windows = SubmissionWindow.has_windows_for_age_group(age_group)
        active_window = SubmissionWindow.get_active_for_age_group(age_group)
        next_window = SubmissionWindow.get_next_upcoming_for_age_group(age_group)

        # Calculate timestamps for frontend countdown timers
        active_window_end_timestamp = None
        if can_submit and active_window and active_window.submission_end:
            active_window_end_timestamp = active_window.submission_end.timestamp()

        next_window_timestamp = None
        if next_window and next_window.submission_start:
            next_window_timestamp = next_window.submission_start.timestamp()

        return SubmissionWindowStatus(
            can_submit=can_submit,
            has_windows=has_windows,
            active_window=active_window,
            next_window=next_window,
            active_window_end_timestamp=active_window_end_timestamp,
            next_window_timestamp=next_window_timestamp,
        )

    @staticmethod
    def to_context_dict(status: SubmissionWindowStatus) -> dict:
        """
        Convert SubmissionWindowStatus to template context dict.

        Args:
            status: The submission window status

        Returns:
            Dictionary suitable for template context
        """
        return {
            "can_submit": status.can_submit,
            "has_windows": status.has_windows,
            "active_window": status.active_window,
            "next_window": status.next_window,
            "next_window_timestamp": status.next_window_timestamp,
            "active_window_end_timestamp": status.active_window_end_timestamp,
        }

    @staticmethod
    def to_json_dict(status: SubmissionWindowStatus) -> dict:
        """
        Convert SubmissionWindowStatus to JSON response dict.

        Args:
            status: The submission window status

        Returns:
            Dictionary suitable for JSON response (no model instances)
        """
        return {
            "can_submit": status.can_submit,
            "has_windows": status.has_windows,
            "next_window_timestamp": status.next_window_timestamp,
            "active_window_end_timestamp": status.active_window_end_timestamp,
        }
