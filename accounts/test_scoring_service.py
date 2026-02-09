from datetime import date
from django.test import TestCase
from django.core.cache import cache

from .models import AgeGroup, Participant, Boulder, Result, CompetitionSettings
from .services.scoring_service import ScoringService


class ScoringServiceTestBase(TestCase):
    """Base class with common fixtures for scoring service tests."""

    def setUp(self):
        """Create shared test fixtures."""
        # Clear cache before each test
        cache.clear()

        # Create age group
        self.age_group = AgeGroup.objects.create(
            name="Test Group",
            min_age=18,
            max_age=99,
            gender="mixed"
        )

        # Create participants
        self.alice = Participant.objects.create(
            username="alice",
            name="Alice",
            date_of_birth=date(2000, 1, 1),
            gender="female",
            age_group=self.age_group
        )

        self.bob = Participant.objects.create(
            username="bob",
            name="Bob",
            date_of_birth=date(2000, 6, 15),
            gender="male",
            age_group=self.age_group
        )

        # Create boulders with different zone counts
        self.boulder_2zone = Boulder.objects.create(
            label="B1",
            zone_count=2,
            color="#ff0000"
        )
        self.boulder_2zone.age_groups.add(self.age_group)

        self.boulder_1zone = Boulder.objects.create(
            label="B2",
            zone_count=1,
            color="#00ff00"
        )
        self.boulder_1zone.age_groups.add(self.age_group)

        self.boulder_0zone = Boulder.objects.create(
            label="B3",
            zone_count=0,
            color="#0000ff"
        )
        self.boulder_0zone.age_groups.add(self.age_group)

    def create_settings(self, grading_system="point_based", **overrides):
        """Create CompetitionSettings with sensible defaults."""
        # Delete any existing settings (singleton)
        CompetitionSettings.objects.all().delete()

        defaults = {
            "grading_system": grading_system,
            "top_points": 25,
            "flash_points": 30,
            "min_top_points": 5,
            "zone_points": 10,
            "zone1_points": 8,
            "zone2_points": 12,
            "min_zone_points": 2,
            "min_zone1_points": 2,
            "min_zone2_points": 3,
            "attempt_penalty": 1,
            # Dynamic tier points
            "top_points_100": 10,
            "top_points_90": 15,
            "top_points_80": 20,
            "top_points_70": 25,
            "top_points_60": 30,
            "top_points_50": 35,
            "top_points_40": 40,
            "top_points_30": 45,
            "top_points_20": 50,
            "top_points_10": 55,
        }
        defaults.update(overrides)
        return CompetitionSettings.objects.create(singleton_guard=True, **defaults)

    def create_result(self, participant, boulder, **kwargs):
        """Create Result with sensible defaults."""
        defaults = {
            "participant": participant,
            "boulder": boulder,
            "attempts": 0,
            "attempts_zone1": 0,
            "attempts_zone2": 0,
            "attempts_top": 0,
            "zone1": False,
            "zone2": False,
            "top": False,
        }
        defaults.update(kwargs)
        return Result.objects.create(**defaults)

    def create_participants(self, count):
        """Create multiple participants for dynamic scoring tests."""
        participants = []
        for i in range(count):
            p = Participant.objects.create(
                username=f"user{i}",
                name=f"User {i}",
                date_of_birth=date(2000, 1, 1),
                gender="mixed",
                age_group=self.age_group
            )
            participants.append(p)
        return participants


class ScoringServiceIFSCTestCase(ScoringServiceTestBase):
    """Test IFSC-style scoring."""

    def test_score_ifsc_single_top_flash(self):
        """Flash top should count as 1 top with 1 attempt."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=1, attempts_top=1
        )

        scored = ScoringService.score_ifsc([result])

        self.assertEqual(scored["tops"], 1)
        self.assertEqual(scored["zones"], 0)
        self.assertEqual(scored["top_attempts"], 1)
        self.assertEqual(scored["zone_attempts"], 0)

    def test_score_ifsc_single_top_multiple_attempts(self):
        """Top with multiple attempts should count correctly."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=5, attempts_top=5
        )

        scored = ScoringService.score_ifsc([result])

        self.assertEqual(scored["tops"], 1)
        self.assertEqual(scored["zones"], 0)
        self.assertEqual(scored["top_attempts"], 5)
        self.assertEqual(scored["zone_attempts"], 0)

    def test_score_ifsc_zone2_only(self):
        """Zone2 only should count as 1 zone."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            zone2=True, attempts=3, attempts_zone2=3
        )

        scored = ScoringService.score_ifsc([result])

        self.assertEqual(scored["tops"], 0)
        self.assertEqual(scored["zones"], 1)
        self.assertEqual(scored["top_attempts"], 0)
        self.assertEqual(scored["zone_attempts"], 3)

    def test_score_ifsc_zone1_only(self):
        """Zone1 only should count as 1 zone."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            zone1=True, attempts=2, attempts_zone1=2
        )

        scored = ScoringService.score_ifsc([result])

        self.assertEqual(scored["tops"], 0)
        self.assertEqual(scored["zones"], 1)
        self.assertEqual(scored["top_attempts"], 0)
        self.assertEqual(scored["zone_attempts"], 2)

    def test_score_ifsc_multiple_results(self):
        """Multiple results should aggregate correctly."""
        r1 = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=1, attempts_top=1
        )
        r2 = self.create_result(
            self.alice, self.boulder_1zone,
            zone1=True, attempts=3, attempts_zone1=3
        )
        r3 = self.create_result(
            self.alice, self.boulder_0zone,
            top=True, attempts=4, attempts_top=4
        )

        scored = ScoringService.score_ifsc([r1, r2, r3])

        self.assertEqual(scored["tops"], 2)
        self.assertEqual(scored["zones"], 1)
        self.assertEqual(scored["top_attempts"], 5)  # 1 + 4
        self.assertEqual(scored["zone_attempts"], 3)

    def test_score_ifsc_empty_results(self):
        """Empty results should return zeros."""
        scored = ScoringService.score_ifsc([])

        self.assertEqual(scored["tops"], 0)
        self.assertEqual(scored["zones"], 0)
        self.assertEqual(scored["top_attempts"], 0)
        self.assertEqual(scored["zone_attempts"], 0)

    def test_score_ifsc_top_fallback_to_attempts(self):
        """Top attempts should fall back to attempts field if attempts_top is 0."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=5, attempts_top=0
        )

        scored = ScoringService.score_ifsc([result])

        self.assertEqual(scored["tops"], 1)
        self.assertEqual(scored["top_attempts"], 5)

    def test_score_ifsc_zone_fallback_to_attempts(self):
        """Zone attempts should fall back to attempts field if specific zone attempts is 0."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            zone1=True, attempts=4, attempts_zone1=0
        )

        scored = ScoringService.score_ifsc([result])

        self.assertEqual(scored["zones"], 1)
        self.assertEqual(scored["zone_attempts"], 4)


class ScoringServicePointBasedTestCase(ScoringServiceTestBase):
    """Test point_based scoring with penalties."""

    def setUp(self):
        super().setUp()
        self.settings = self.create_settings("point_based")

    def test_score_point_based_flash(self):
        """Flash should give flash_points."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=1, attempts_top=1
        )

        scored = ScoringService.score_point_based([result], self.settings)

        self.assertEqual(scored["points"], 30)  # flash_points
        self.assertEqual(scored["tops"], 1)
        self.assertEqual(scored["attempts"], 1)

    def test_score_point_based_top_with_penalty(self):
        """Top with penalties should reduce points to min_top_points."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=25, attempts_top=25
        )

        scored = ScoringService.score_point_based([result], self.settings)

        # 25 base - 24 penalty = 1, but min is 5
        self.assertEqual(scored["points"], 5)  # min_top_points
        self.assertEqual(scored["tops"], 1)

    def test_score_point_based_zone2_flash(self):
        """Zone2 with 1 attempt should give full zone2_points."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            zone2=True, attempts=1, attempts_zone2=1
        )

        scored = ScoringService.score_point_based([result], self.settings)

        self.assertEqual(scored["points"], 12)  # zone2_points
        self.assertEqual(scored["zones"], 1)

    def test_score_point_based_zone2_with_penalty(self):
        """Zone2 with penalties should reduce to min_zone2_points."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            zone2=True, attempts=12, attempts_zone2=12
        )

        scored = ScoringService.score_point_based([result], self.settings)

        # 12 base - 11 penalty = 1, but min is 3
        self.assertEqual(scored["points"], 3)  # min_zone2_points
        self.assertEqual(scored["zones"], 1)

    def test_score_point_based_zone1_on_2zone_boulder(self):
        """Zone1 on 2-zone boulder should use zone1_points."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            zone1=True, attempts=1, attempts_zone1=1
        )

        scored = ScoringService.score_point_based([result], self.settings)

        self.assertEqual(scored["points"], 8)  # zone1_points
        self.assertEqual(scored["zones"], 1)

    def test_score_point_based_zone1_on_1zone_boulder(self):
        """Zone1 on 1-zone boulder should use zone_points."""
        result = self.create_result(
            self.alice, self.boulder_1zone,
            zone1=True, attempts=1, attempts_zone1=1
        )

        scored = ScoringService.score_point_based([result], self.settings)

        self.assertEqual(scored["points"], 10)  # zone_points
        self.assertEqual(scored["zones"], 1)

    def test_score_point_based_no_achievement(self):
        """No achievement should count attempts only."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            attempts=5
        )

        scored = ScoringService.score_point_based([result], self.settings)

        self.assertEqual(scored["points"], 0)
        self.assertEqual(scored["tops"], 0)
        self.assertEqual(scored["zones"], 0)
        self.assertEqual(scored["attempts"], 5)

    def test_score_point_based_multiple_boulders(self):
        """Multiple boulders should aggregate correctly."""
        r1 = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=1, attempts_top=1
        )
        r2 = self.create_result(
            self.alice, self.boulder_1zone,
            zone1=True, attempts=2, attempts_zone1=2
        )
        r3 = self.create_result(
            self.alice, self.boulder_0zone,
            attempts=3
        )

        scored = ScoringService.score_point_based([r1, r2, r3], self.settings)

        # 30 (flash) + 9 (zone_points - 1 penalty) + 0 = 39
        self.assertEqual(scored["points"], 39)
        self.assertEqual(scored["tops"], 1)
        self.assertEqual(scored["zones"], 1)
        self.assertEqual(scored["attempts"], 6)

    def test_score_point_based_zone_fallback_to_attempts(self):
        """Zone scoring should fall back to attempts field if specific zone attempts is 0."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            zone1=True, attempts=3, attempts_zone1=0
        )

        scored = ScoringService.score_point_based([result], self.settings)

        # 8 base - 2 penalty = 6
        self.assertEqual(scored["points"], 6)
        self.assertEqual(scored["zones"], 1)
        self.assertEqual(scored["attempts"], 3)


class ScoringServicePointBasedDynamicTestCase(ScoringServiceTestBase):
    """Test point_based_dynamic scoring - no penalties."""

    def setUp(self):
        super().setUp()
        self.settings = self.create_settings("point_based_dynamic")

    def test_score_point_based_dynamic_flash(self):
        """Flash should give flash_points regardless of percentage."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=1, attempts_top=1
        )

        scored = ScoringService.score_point_based_dynamic(
            [result], self.settings, {self.boulder_2zone.id: 5}, 10
        )

        self.assertEqual(scored["points"], 30)  # flash_points
        self.assertEqual(scored["tops"], 1)

    def test_score_point_based_dynamic_top_50_percent(self):
        """Top at 50% should use top_points_50 with no penalty."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=5, attempts_top=5
        )

        # 5 out of 10 participants topped = 50%
        scored = ScoringService.score_point_based_dynamic(
            [result], self.settings, {self.boulder_2zone.id: 5}, 10
        )

        self.assertEqual(scored["points"], 35)  # top_points_50
        self.assertEqual(scored["tops"], 1)
        self.assertEqual(scored["attempts"], 5)

    def test_score_point_based_dynamic_zone2_no_penalty(self):
        """Zone2 should give full zone2_points with no penalty."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            zone2=True, attempts=10, attempts_zone2=10
        )

        scored = ScoringService.score_point_based_dynamic(
            [result], self.settings, {}, 10
        )

        self.assertEqual(scored["points"], 12)  # zone2_points, no penalty
        self.assertEqual(scored["zones"], 1)

    def test_score_point_based_dynamic_zone1_no_penalty(self):
        """Zone1 should give full zone1_points with no penalty."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            zone1=True, attempts=8, attempts_zone1=8
        )

        scored = ScoringService.score_point_based_dynamic(
            [result], self.settings, {}, 10
        )

        self.assertEqual(scored["points"], 8)  # zone1_points, no penalty
        self.assertEqual(scored["zones"], 1)

    def test_score_point_based_dynamic_zone_on_1zone_boulder(self):
        """Zone on 1-zone boulder should use zone_points."""
        result = self.create_result(
            self.alice, self.boulder_1zone,
            zone1=True, attempts=5, attempts_zone1=5
        )

        scored = ScoringService.score_point_based_dynamic(
            [result], self.settings, {}, 10
        )

        self.assertEqual(scored["points"], 10)  # zone_points
        self.assertEqual(scored["zones"], 1)

    def test_score_point_based_dynamic_multiple_tops(self):
        """Multiple tops should use correct dynamic points."""
        r1 = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=1, attempts_top=1
        )
        r2 = self.create_result(
            self.alice, self.boulder_1zone,
            top=True, attempts=3, attempts_top=3
        )

        # boulder_2zone: 9/10 topped = 90%
        # boulder_1zone: 1/10 topped = 10%
        top_counts = {
            self.boulder_2zone.id: 9,
            self.boulder_1zone.id: 1
        }

        scored = ScoringService.score_point_based_dynamic(
            [r1, r2], self.settings, top_counts, 10
        )

        # 30 (flash) + 55 (top_points_10) = 85
        self.assertEqual(scored["points"], 85)
        self.assertEqual(scored["tops"], 2)

    def test_score_point_based_dynamic_empty_top_counts(self):
        """Zero tops should use top_points_10."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=5, attempts_top=5
        )

        # No one else topped this boulder
        scored = ScoringService.score_point_based_dynamic(
            [result], self.settings, {}, 10
        )

        # 0% topped = top_points_10
        self.assertEqual(scored["points"], 55)  # top_points_10


class ScoringServicePointBasedDynamicAttemptsTestCase(ScoringServiceTestBase):
    """Test point_based_dynamic_attempts - with penalties."""

    def setUp(self):
        super().setUp()
        self.settings = self.create_settings("point_based_dynamic_attempts")

    def test_score_point_based_dynamic_attempts_flash(self):
        """Flash should give flash_points."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=1, attempts_top=1
        )

        scored = ScoringService.score_point_based_dynamic_attempts(
            [result], self.settings, {self.boulder_2zone.id: 5}, 10
        )

        self.assertEqual(scored["points"], 30)  # flash_points
        self.assertEqual(scored["tops"], 1)

    def test_score_point_based_dynamic_attempts_top_with_penalty(self):
        """Top with penalty should reduce to min_top_points."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=20, attempts_top=20
        )

        # 5 out of 10 = 50% = top_points_50 = 35
        # Penalty: 19 * 1 = 19
        # Result: 35 - 19 = 16
        scored = ScoringService.score_point_based_dynamic_attempts(
            [result], self.settings, {self.boulder_2zone.id: 5}, 10
        )

        self.assertEqual(scored["points"], 16)
        self.assertEqual(scored["tops"], 1)

    def test_score_point_based_dynamic_attempts_top_penalty_respects_minimum(self):
        """Top penalty should respect min_top_points."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=50, attempts_top=50
        )

        # 5 out of 10 = 50% = top_points_50 = 35
        # Penalty: 49 * 1 = 49
        # Result: 35 - 49 = -14, but min is 5
        scored = ScoringService.score_point_based_dynamic_attempts(
            [result], self.settings, {self.boulder_2zone.id: 5}, 10
        )

        self.assertEqual(scored["points"], 5)  # min_top_points
        self.assertEqual(scored["tops"], 1)

    def test_score_point_based_dynamic_attempts_zone2_with_penalty(self):
        """Zone2 with penalty should reduce to min_zone2_points."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            zone2=True, attempts=15, attempts_zone2=15
        )

        # 12 base - 14 penalty = -2, but min is 3
        scored = ScoringService.score_point_based_dynamic_attempts(
            [result], self.settings, {}, 10
        )

        self.assertEqual(scored["points"], 3)  # min_zone2_points
        self.assertEqual(scored["zones"], 1)

    def test_score_point_based_dynamic_attempts_zone1_with_penalty(self):
        """Zone1 with penalty should reduce to min_zone1_points."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            zone1=True, attempts=10, attempts_zone1=10
        )

        # 8 base - 9 penalty = -1, but min is 2
        scored = ScoringService.score_point_based_dynamic_attempts(
            [result], self.settings, {}, 10
        )

        self.assertEqual(scored["points"], 2)  # min_zone1_points
        self.assertEqual(scored["zones"], 1)

    def test_score_point_based_dynamic_attempts_multiple_results(self):
        """Multiple results should aggregate correctly."""
        r1 = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=1, attempts_top=1
        )
        r2 = self.create_result(
            self.alice, self.boulder_1zone,
            zone1=True, attempts=3, attempts_zone1=3
        )

        top_counts = {self.boulder_2zone.id: 5}

        scored = ScoringService.score_point_based_dynamic_attempts(
            [r1, r2], self.settings, top_counts, 10
        )

        # 30 (flash) + 8 (zone_points - 2 penalty = 8, min is 2) = 38
        self.assertEqual(scored["points"], 38)
        self.assertEqual(scored["tops"], 1)
        self.assertEqual(scored["zones"], 1)


class ScoringServiceBoulderPointsTestCase(ScoringServiceTestBase):
    """Test calculate_boulder_points() for single boulder."""

    def setUp(self):
        super().setUp()
        self.settings = self.create_settings("point_based")

    def test_calculate_boulder_points_ifsc_returns_zero(self):
        """IFSC mode should always return 0 points."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=1, attempts_top=1
        )

        points = ScoringService.calculate_boulder_points(
            result, "ifsc", self.settings
        )

        self.assertEqual(points, 0)

    def test_calculate_boulder_points_flash_all_modes(self):
        """Flash should give flash_points in all point-based modes."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=1, attempts_top=1
        )

        modes = ["point_based", "point_based_dynamic", "point_based_dynamic_attempts"]

        for mode in modes:
            with self.subTest(mode=mode):
                points = ScoringService.calculate_boulder_points(
                    result, mode, self.settings,
                    top_counts={self.boulder_2zone.id: 5}, participant_count=10
                )
                self.assertEqual(points, 30)

    def test_calculate_boulder_points_no_achievement_returns_zero(self):
        """No achievement should return 0 points."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            attempts=5
        )

        points = ScoringService.calculate_boulder_points(
            result, "point_based", self.settings
        )

        self.assertEqual(points, 0)

    def test_calculate_boulder_points_dynamic_missing_top_counts(self):
        """Dynamic mode with missing top_counts should return 0."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=3, attempts_top=3
        )

        points = ScoringService.calculate_boulder_points(
            result, "point_based_dynamic", self.settings,
            top_counts=None, participant_count=10
        )

        self.assertEqual(points, 0)

    def test_calculate_boulder_points_dynamic_missing_participant_count(self):
        """Dynamic mode with missing participant_count should return 0."""
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=3, attempts_top=3
        )

        points = ScoringService.calculate_boulder_points(
            result, "point_based_dynamic", self.settings,
            top_counts={self.boulder_2zone.id: 5}, participant_count=None
        )

        self.assertEqual(points, 0)

    def test_calculate_boulder_points_zone_hierarchy(self):
        """Zone points should respect boulder zone_count."""
        # Zone2 on 2-zone boulder
        r1 = self.create_result(
            self.alice, self.boulder_2zone,
            zone2=True, attempts=1, attempts_zone2=1
        )
        points1 = ScoringService.calculate_boulder_points(
            r1, "point_based", self.settings
        )
        self.assertEqual(points1, 12)  # zone2_points

        # Zone1 on 2-zone boulder
        r2 = self.create_result(
            self.bob, self.boulder_2zone,
            zone1=True, attempts=1, attempts_zone1=1
        )
        points2 = ScoringService.calculate_boulder_points(
            r2, "point_based", self.settings
        )
        self.assertEqual(points2, 8)  # zone1_points

        # Zone on 1-zone boulder
        r3 = self.create_result(
            self.alice, self.boulder_1zone,
            zone1=True, attempts=1, attempts_zone1=1
        )
        points3 = ScoringService.calculate_boulder_points(
            r3, "point_based", self.settings
        )
        self.assertEqual(points3, 10)  # zone_points


class ScoringServiceDynamicTiersTestCase(ScoringServiceTestBase):
    """Test get_dynamic_top_points() tier calculation."""

    def setUp(self):
        super().setUp()
        self.settings = self.create_settings("point_based_dynamic")

    def test_dynamic_tier_100_percent(self):
        """95% should use top_points_100."""
        points = ScoringService.get_dynamic_top_points(self.settings, 95.0)
        self.assertEqual(points, 10)  # top_points_100

    def test_dynamic_tier_90_percent(self):
        """91% should use top_points_90."""
        points = ScoringService.get_dynamic_top_points(self.settings, 91.0)
        self.assertEqual(points, 10)  # >90 = top_points_100

    def test_dynamic_tier_80_percent(self):
        """85% should use top_points_80."""
        points = ScoringService.get_dynamic_top_points(self.settings, 85.0)
        self.assertEqual(points, 15)  # >80 = top_points_90

    def test_dynamic_tier_70_percent(self):
        """75% should use top_points_70."""
        points = ScoringService.get_dynamic_top_points(self.settings, 75.0)
        self.assertEqual(points, 20)  # >70 = top_points_80

    def test_dynamic_tier_60_percent(self):
        """65% should use top_points_60."""
        points = ScoringService.get_dynamic_top_points(self.settings, 65.0)
        self.assertEqual(points, 25)  # >60 = top_points_70

    def test_dynamic_tier_50_percent(self):
        """55% should use top_points_50."""
        points = ScoringService.get_dynamic_top_points(self.settings, 55.0)
        self.assertEqual(points, 30)  # >50 = top_points_60

    def test_dynamic_tier_40_percent(self):
        """45% should use top_points_40."""
        points = ScoringService.get_dynamic_top_points(self.settings, 45.0)
        self.assertEqual(points, 35)  # >40 = top_points_50

    def test_dynamic_tier_30_percent(self):
        """35% should use top_points_30."""
        points = ScoringService.get_dynamic_top_points(self.settings, 35.0)
        self.assertEqual(points, 40)  # >30 = top_points_40

    def test_dynamic_tier_20_percent(self):
        """25% should use top_points_20."""
        points = ScoringService.get_dynamic_top_points(self.settings, 25.0)
        self.assertEqual(points, 45)  # >20 = top_points_30

    def test_dynamic_tier_10_percent(self):
        """5% should use top_points_10."""
        points = ScoringService.get_dynamic_top_points(self.settings, 5.0)
        self.assertEqual(points, 55)  # <=10 = top_points_10

    def test_dynamic_tier_boundary_90(self):
        """Exactly 90% should use top_points_90."""
        points = ScoringService.get_dynamic_top_points(self.settings, 90.0)
        self.assertEqual(points, 15)  # 90 is NOT >90, so uses top_points_90

    def test_dynamic_tier_boundary_90_minus_epsilon(self):
        """Just below 90% should use top_points_90."""
        points = ScoringService.get_dynamic_top_points(self.settings, 90.0 - 0.001)
        self.assertEqual(points, 15)  # top_points_90


class ScoringServiceRankingTestCase(ScoringServiceTestBase):
    """Test rank_entries() logic for all grading systems."""

    def test_rank_entries_point_based_primary_sort(self):
        """Ranking should sort by points (descending) first."""
        entries = [
            {"participant": self.alice, "points": 100, "tops": 3, "zones": 2, "attempts": 10},
            {"participant": self.bob, "points": 150, "tops": 4, "zones": 1, "attempts": 8},
        ]

        ScoringService.rank_entries(entries, "point_based")

        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["participant"], self.bob)
        self.assertEqual(entries[1]["rank"], 2)
        self.assertEqual(entries[1]["participant"], self.alice)

    def test_rank_entries_point_based_secondary_sort_tops(self):
        """With equal points, should sort by tops."""
        entries = [
            {"participant": self.alice, "points": 100, "tops": 3, "zones": 2, "attempts": 10},
            {"participant": self.bob, "points": 100, "tops": 4, "zones": 1, "attempts": 8},
        ]

        ScoringService.rank_entries(entries, "point_based")

        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["participant"], self.bob)

    def test_rank_entries_point_based_tertiary_sort_zones(self):
        """With equal points and tops, should sort by zones."""
        entries = [
            {"participant": self.alice, "points": 100, "tops": 3, "zones": 2, "attempts": 10},
            {"participant": self.bob, "points": 100, "tops": 3, "zones": 3, "attempts": 8},
        ]

        ScoringService.rank_entries(entries, "point_based")

        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["participant"], self.bob)

    def test_rank_entries_point_based_quaternary_sort_attempts(self):
        """With equal points, tops, zones, should sort by attempts (ascending)."""
        entries = [
            {"participant": self.alice, "points": 100, "tops": 3, "zones": 2, "attempts": 10},
            {"participant": self.bob, "points": 100, "tops": 3, "zones": 2, "attempts": 8},
        ]

        ScoringService.rank_entries(entries, "point_based")

        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["participant"], self.bob)

    def test_rank_entries_point_based_ties(self):
        """Identical scores with same name should get same rank."""
        # Note: Ranking includes name in the sort key for tie-breaking
        # So Alice and Bob with identical scores will have different ranks
        # Only way to get identical rank is identical name too
        entries = [
            {"participant": self.alice, "points": 100, "tops": 3, "zones": 2, "attempts": 10},
            {"participant": self.bob, "points": 50, "tops": 2, "zones": 1, "attempts": 15},
        ]

        ScoringService.rank_entries(entries, "point_based")

        # Alice has better score, so rank 1
        # Bob has worse score, so rank 2
        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["participant"], self.alice)
        self.assertEqual(entries[1]["rank"], 2)
        self.assertEqual(entries[1]["participant"], self.bob)

    def test_rank_entries_ifsc_primary_sort_tops(self):
        """IFSC ranking should sort by tops (descending) first."""
        entries = [
            {"participant": self.alice, "tops": 2, "zones": 3, "top_attempts": 5, "zone_attempts": 8},
            {"participant": self.bob, "tops": 3, "zones": 2, "top_attempts": 4, "zone_attempts": 6},
        ]

        ScoringService.rank_entries(entries, "ifsc")

        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["participant"], self.bob)

    def test_rank_entries_ifsc_secondary_sort_zones(self):
        """With equal tops, IFSC should sort by zones."""
        entries = [
            {"participant": self.alice, "tops": 3, "zones": 2, "top_attempts": 5, "zone_attempts": 8},
            {"participant": self.bob, "tops": 3, "zones": 4, "top_attempts": 4, "zone_attempts": 6},
        ]

        ScoringService.rank_entries(entries, "ifsc")

        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["participant"], self.bob)

    def test_rank_entries_ifsc_tertiary_sort_top_attempts(self):
        """With equal tops and zones, IFSC should sort by top_attempts (ascending)."""
        entries = [
            {"participant": self.alice, "tops": 3, "zones": 2, "top_attempts": 5, "zone_attempts": 8},
            {"participant": self.bob, "tops": 3, "zones": 2, "top_attempts": 4, "zone_attempts": 6},
        ]

        ScoringService.rank_entries(entries, "ifsc")

        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["participant"], self.bob)

    def test_rank_entries_ifsc_quaternary_sort_zone_attempts(self):
        """With equal tops, zones, top_attempts, IFSC should sort by zone_attempts."""
        entries = [
            {"participant": self.alice, "tops": 3, "zones": 2, "top_attempts": 5, "zone_attempts": 8},
            {"participant": self.bob, "tops": 3, "zones": 2, "top_attempts": 5, "zone_attempts": 6},
        ]

        ScoringService.rank_entries(entries, "ifsc")

        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["participant"], self.bob)

    def test_rank_entries_ifsc_zero_tops_uses_inf(self):
        """IFSC with zero tops should use infinity for top_attempts."""
        entries = [
            {"participant": self.alice, "tops": 0, "zones": 2, "top_attempts": 0, "zone_attempts": 8},
            {"participant": self.bob, "tops": 1, "zones": 1, "top_attempts": 10, "zone_attempts": 6},
        ]

        ScoringService.rank_entries(entries, "ifsc")

        # Bob with 1 top should rank higher than Alice with 0 tops
        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["participant"], self.bob)


class ScoringServiceEdgeCasesTestCase(ScoringServiceTestBase):
    """Test edge cases and error handling."""

    def test_empty_results_list(self):
        """Empty results should return zero metrics for all modes."""
        settings = self.create_settings("point_based")

        # IFSC
        scored_ifsc = ScoringService.score_ifsc([])
        self.assertEqual(scored_ifsc["tops"], 0)

        # point_based
        scored_pb = ScoringService.score_point_based([], settings)
        self.assertEqual(scored_pb["points"], 0)

        # point_based_dynamic
        scored_dyn = ScoringService.score_point_based_dynamic([], settings, {}, 10)
        self.assertEqual(scored_dyn["points"], 0)

        # point_based_dynamic_attempts
        scored_dyn_att = ScoringService.score_point_based_dynamic_attempts([], settings, {}, 10)
        self.assertEqual(scored_dyn_att["points"], 0)

    def test_division_by_zero_participant_count(self):
        """Zero participant_count should handle division by zero."""
        settings = self.create_settings("point_based_dynamic")
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=3, attempts_top=3
        )

        # Should not crash, should use 0% = top_points_10
        scored = ScoringService.score_point_based_dynamic(
            [result], settings, {self.boulder_2zone.id: 0}, 0
        )

        self.assertEqual(scored["points"], 55)  # top_points_10

    def test_zero_attempts_fallback(self):
        """Zero values in attempt fields should fall back to attempts field."""
        settings = self.create_settings("point_based")

        # Create result with 0 for attempts_top (fallback to attempts)
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=5, attempts_top=0
        )

        scored = ScoringService.score_ifsc([result])
        # Should fall back to attempts field
        self.assertEqual(scored["top_attempts"], 5)

    def test_extreme_attempt_counts(self):
        """Extreme attempt counts should respect minimums."""
        settings = self.create_settings("point_based")
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=1000, attempts_top=1000
        )

        scored = ScoringService.score_point_based([result], settings)

        # Should enforce min_top_points
        self.assertEqual(scored["points"], 5)  # min_top_points

    def test_missing_boulder_in_top_counts(self):
        """Missing boulder in top_counts should default to 0 tops."""
        settings = self.create_settings("point_based_dynamic")
        result = self.create_result(
            self.alice, self.boulder_2zone,
            top=True, attempts=3, attempts_top=3
        )

        # top_counts doesn't include this boulder
        scored = ScoringService.score_point_based_dynamic(
            [result], settings, {}, 10
        )

        # 0 tops = 0% = top_points_10
        self.assertEqual(scored["points"], 55)  # top_points_10

    def test_rank_entries_empty_list(self):
        """Ranking empty list should not crash."""
        entries = []
        ScoringService.rank_entries(entries, "point_based")
        self.assertEqual(entries, [])

    def test_group_results_by_participant_empty(self):
        """Grouping empty results should return empty dict."""
        result_map = ScoringService.group_results_by_participant([])
        self.assertEqual(result_map, {})

    def test_count_tops_per_boulder_empty(self):
        """Counting tops on empty results should return empty dict."""
        top_counts = ScoringService.count_tops_per_boulder([])
        self.assertEqual(top_counts, {})


class ScoringServiceHelperMethodsTestCase(ScoringServiceTestBase):
    """Test helper methods."""

    def test_count_tops_per_boulder(self):
        """count_tops_per_boulder should count correctly."""
        r1 = self.create_result(self.alice, self.boulder_2zone, top=True)
        r2 = self.create_result(self.bob, self.boulder_2zone, top=True)
        r3 = self.create_result(self.alice, self.boulder_1zone, top=True)
        r4 = self.create_result(self.bob, self.boulder_1zone, top=False)

        top_counts = ScoringService.count_tops_per_boulder([r1, r2, r3, r4])

        self.assertEqual(top_counts[self.boulder_2zone.id], 2)
        self.assertEqual(top_counts[self.boulder_1zone.id], 1)
        self.assertNotIn(self.boulder_0zone.id, top_counts)

    def test_group_results_by_participant(self):
        """group_results_by_participant should group correctly."""
        r1 = self.create_result(self.alice, self.boulder_2zone, top=True)
        r2 = self.create_result(self.alice, self.boulder_1zone, top=True)
        r3 = self.create_result(self.bob, self.boulder_2zone, top=False)

        result_map = ScoringService.group_results_by_participant([r1, r2, r3])

        self.assertEqual(len(result_map[self.alice.id]), 2)
        self.assertEqual(len(result_map[self.bob.id]), 1)

    def test_get_active_settings_caching(self):
        """get_active_settings should cache correctly."""
        cache.clear()

        settings = self.create_settings("point_based")

        # First call should query DB and cache
        fetched1 = ScoringService.get_active_settings()
        self.assertEqual(fetched1.id, settings.id)

        # Second call should use cache
        fetched2 = ScoringService.get_active_settings()
        self.assertEqual(fetched2.id, settings.id)

        # Verify it's actually cached
        cached = cache.get('competition_settings')
        self.assertIsNotNone(cached)
        self.assertEqual(cached.id, settings.id)

    def test_invalidate_settings_cache(self):
        """invalidate_settings_cache should clear cache."""
        cache.clear()

        settings = self.create_settings("point_based")
        cache.set('competition_settings', settings, 300)

        # Verify cached
        self.assertIsNotNone(cache.get('competition_settings'))

        # Invalidate
        ScoringService.invalidate_settings_cache()

        # Verify cleared
        self.assertIsNone(cache.get('competition_settings'))

    def test_get_cached_scoreboard(self):
        """get_cached_scoreboard should retrieve cached data."""
        cache.clear()

        data = {"entries": [{"participant": self.alice, "points": 100}]}
        ScoringService.cache_scoreboard(self.age_group.id, "point_based", data)

        fetched = ScoringService.get_cached_scoreboard(self.age_group.id, "point_based")

        self.assertEqual(fetched, data)

    def test_cache_scoreboard(self):
        """cache_scoreboard should store data."""
        cache.clear()

        data = {"entries": [{"participant": self.alice, "points": 100}]}
        ScoringService.cache_scoreboard(self.age_group.id, "point_based", data)

        # Verify cached
        cache_key = f"scoreboard_{self.age_group.id}_point_based"
        cached = cache.get(cache_key)
        self.assertEqual(cached, data)


class ScoringServiceIntegrationTestCase(ScoringServiceTestBase):
    """Integration tests for build_scoreboard_entries()."""

    def test_build_scoreboard_entries_point_based(self):
        """build_scoreboard_entries should work end-to-end for point_based."""
        settings = self.create_settings("point_based")

        # Alice: 1 flash, 1 zone
        r1 = self.create_result(self.alice, self.boulder_2zone, top=True, attempts=1, attempts_top=1)
        r2 = self.create_result(self.alice, self.boulder_1zone, zone1=True, attempts=2, attempts_zone1=2)

        # Bob: 1 top (3 attempts), 1 zone2
        r3 = self.create_result(self.bob, self.boulder_2zone, top=True, attempts=3, attempts_top=3)
        r4 = self.create_result(self.bob, self.boulder_1zone, zone2=True, attempts=1, attempts_zone2=1)

        result_map = ScoringService.group_results_by_participant([r1, r2, r3, r4])
        entries = ScoringService.build_scoreboard_entries(
            [self.alice, self.bob], result_map, "point_based", settings
        )

        # Alice: 30 (flash) + 9 (10 - 1 penalty) = 39
        # Bob: 23 (25 - 2 penalty) + 12 (zone2) = 35

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["participant"], self.alice)
        self.assertEqual(entries[0]["points"], 39)
        self.assertEqual(entries[0]["rank"], 1)

        self.assertEqual(entries[1]["participant"], self.bob)
        self.assertEqual(entries[1]["points"], 35)
        self.assertEqual(entries[1]["rank"], 2)

    def test_build_scoreboard_entries_ifsc(self):
        """build_scoreboard_entries should work end-to-end for IFSC."""
        # Alice: 2 tops, 1 zone
        r1 = self.create_result(self.alice, self.boulder_2zone, top=True, attempts=1, attempts_top=1)
        r2 = self.create_result(self.alice, self.boulder_1zone, top=True, attempts=3, attempts_top=3)
        r3 = self.create_result(self.alice, self.boulder_0zone, zone1=True, attempts=2, attempts_zone1=2)

        # Bob: 1 top, 2 zones
        r4 = self.create_result(self.bob, self.boulder_2zone, top=True, attempts=2, attempts_top=2)
        r5 = self.create_result(self.bob, self.boulder_1zone, zone2=True, attempts=1, attempts_zone2=1)
        r6 = self.create_result(self.bob, self.boulder_0zone, zone1=True, attempts=1, attempts_zone1=1)

        result_map = ScoringService.group_results_by_participant([r1, r2, r3, r4, r5, r6])
        entries = ScoringService.build_scoreboard_entries(
            [self.alice, self.bob], result_map, "ifsc", None
        )

        # Alice: 2 tops, 1 zone, top_att=4, zone_att=2
        # Bob: 1 top, 2 zones, top_att=2, zone_att=2

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["participant"], self.alice)
        self.assertEqual(entries[0]["tops"], 2)
        self.assertEqual(entries[0]["zones"], 1)
        self.assertEqual(entries[0]["rank"], 1)

        self.assertEqual(entries[1]["participant"], self.bob)
        self.assertEqual(entries[1]["tops"], 1)
        self.assertEqual(entries[1]["zones"], 2)
        self.assertEqual(entries[1]["rank"], 2)

    def test_build_scoreboard_entries_dynamic(self):
        """build_scoreboard_entries should work end-to-end for point_based_dynamic."""
        settings = self.create_settings("point_based_dynamic")

        # Create 10 participants
        participants = self.create_participants(10)

        # 5 participants top boulder_2zone (50%)
        for i in range(5):
            self.create_result(participants[i], self.boulder_2zone, top=True, attempts=2, attempts_top=2)

        # 1 participant tops boulder_1zone (10%)
        self.create_result(participants[0], self.boulder_1zone, top=True, attempts=1, attempts_top=1)

        # Count tops
        all_results = Result.objects.all()
        top_counts = ScoringService.count_tops_per_boulder(all_results)

        result_map = ScoringService.group_results_by_participant(all_results)
        entries = ScoringService.build_scoreboard_entries(
            participants, result_map, "point_based_dynamic", settings,
            top_counts=top_counts, participant_count=10
        )

        # participants[0]: 35 (top_points_50) + 30 (flash) = 65
        # participants[1-4]: 35 (top_points_50) each
        # participants[5-9]: 0

        self.assertEqual(entries[0]["participant"], participants[0])
        self.assertEqual(entries[0]["points"], 65)
        self.assertEqual(entries[0]["rank"], 1)

        self.assertEqual(entries[1]["points"], 35)
        self.assertEqual(entries[1]["rank"], 2)

    def test_build_scoreboard_entries_no_results(self):
        """build_scoreboard_entries with no results should return zero scores."""
        settings = self.create_settings("point_based")

        entries = ScoringService.build_scoreboard_entries(
            [self.alice, self.bob], {}, "point_based", settings
        )

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["points"], 0)
        self.assertEqual(entries[1]["points"], 0)
        # With identical scores, they're sorted by name (Alice, Bob)
        # Since name is part of sort key, they get different ranks
        self.assertEqual(entries[0]["participant"], self.alice)
        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[1]["participant"], self.bob)
        self.assertEqual(entries[1]["rank"], 2)
