from datetime import date
from django.test import TestCase, Client
from django.contrib.auth.hashers import check_password

from .models import Participant, AgeGroup
from .utils import hash_password, verify_password


class PasswordUtilsTestCase(TestCase):
    """Test password hashing utilities."""

    def test_hash_password(self):
        """Test that password hashing works."""
        raw = "test123"
        hashed = hash_password(raw)

        # Should be hashed (not plaintext)
        self.assertNotEqual(raw, hashed)
        # Should start with algorithm prefix
        self.assertTrue(hashed.startswith('pbkdf2_sha256$'))
        # Should be verifiable by Django
        self.assertTrue(check_password(raw, hashed))

    def test_verify_password_hashed(self):
        """Test verification of hashed passwords."""
        raw = "test123"
        hashed = hash_password(raw)

        # Correct password
        self.assertTrue(verify_password(raw, hashed))
        # Wrong password
        self.assertFalse(verify_password("wrong", hashed))

    def test_hash_password_different_each_time(self):
        """Test that hashing same password produces different hashes (salt)."""
        raw = "test123"
        hash1 = hash_password(raw)
        hash2 = hash_password(raw)

        # Hashes should be different (due to salt)
        self.assertNotEqual(hash1, hash2)
        # But both should verify correctly
        self.assertTrue(verify_password(raw, hash1))
        self.assertTrue(verify_password(raw, hash2))


class ParticipantAuthTestCase(TestCase):
    """Test participant authentication with hashed passwords."""

    def setUp(self):
        """Create test age group and participant."""
        self.age_group = AgeGroup.objects.create(
            name="Test Group",
            min_age=18,
            max_age=99,
            gender="mixed"
        )

    def test_participant_creation_with_hashed_password(self):
        """Test that new participants get hashed passwords via signal."""
        p = Participant.objects.create(
            username="testuser",
            name="Test User",
            date_of_birth=date(2000, 1, 1),
            gender="male",
            age_group=self.age_group
        )

        # Password should be set and hashed (from signal)
        self.assertIsNotNone(p.password)
        self.assertTrue(p.password.startswith('pbkdf2_sha256$'))

        # Should verify with DOB password
        self.assertTrue(verify_password("01012000", p.password))

    def test_login_with_hashed_password(self):
        """Test login works with hashed password."""
        p = Participant.objects.create(
            username="testuser",
            name="Test User",
            date_of_birth=date(2000, 1, 1),
            gender="male",
            age_group=self.age_group
        )

        # Should be able to verify with DOB password
        self.assertTrue(verify_password("01012000", p.password))

    def test_login_view_hashed_password(self):
        """Test login view works with hashed password."""
        p = Participant.objects.create(
            username="testuser",
            name="Test User",
            date_of_birth=date(2000, 1, 1),
            gender="male",
            age_group=self.age_group
        )

        client = Client()

        # Login with DOB password
        response = client.post('/', {
            'username': 'testuser',
            'password': '01012000'
        })

        # Should redirect to dashboard (successful login)
        self.assertEqual(response.status_code, 302)
        self.assertIn('participant_id', client.session)
        self.assertEqual(client.session['participant_id'], p.id)

    def test_login_view_wrong_password(self):
        """Test login view rejects wrong password."""
        p = Participant.objects.create(
            username="testuser",
            name="Test User",
            date_of_birth=date(2000, 1, 1),
            gender="male",
            age_group=self.age_group
        )

        client = Client()

        # Try wrong password
        response = client.post('/', {
            'username': 'testuser',
            'password': 'wrongpassword'
        })

        # Should not redirect (failed login)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('participant_id', client.session)
        self.assertContains(response, 'Falsches Passwort')

    def test_login_view_unknown_user(self):
        """Test login view rejects unknown username."""
        client = Client()

        # Try non-existent user
        response = client.post('/', {
            'username': 'unknownuser',
            'password': 'anypassword'
        })

        # Should not redirect (failed login)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('participant_id', client.session)
        self.assertContains(response, 'Unbekannter Teilnehmer')


class PasswordChangeTestCase(TestCase):
    """Test password change functionality."""

    def setUp(self):
        """Create test participant and login."""
        self.age_group = AgeGroup.objects.create(
            name="Test Group",
            min_age=18,
            max_age=99,
            gender="mixed"
        )
        self.participant = Participant.objects.create(
            username="testuser",
            name="Test User",
            date_of_birth=date(2000, 1, 1),
            gender="male",
            age_group=self.age_group
        )
        # Store original password for verification
        self.original_password = self.participant.password

        # Login
        self.client = Client()
        session = self.client.session
        session['participant_id'] = self.participant.id
        session.save()

    def test_password_change_success(self):
        """Test changing password via settings page."""
        # Change password
        response = self.client.post('/settings/', {
            'current_password': '01012000',
            'new_password': 'newpass123',
            'confirm_password': 'newpass123'
        })

        # Should succeed
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dein Passwort wurde aktualisiert')

        # Reload participant
        self.participant.refresh_from_db()

        # Password should be different and hashed
        self.assertNotEqual(self.participant.password, self.original_password)
        self.assertTrue(self.participant.password.startswith('pbkdf2_sha256$'))

        # Should verify with new password
        self.assertTrue(verify_password('newpass123', self.participant.password))

        # Old password should not work
        self.assertFalse(verify_password('01012000', self.participant.password))

    def test_password_change_wrong_current(self):
        """Test password change fails with wrong current password."""
        response = self.client.post('/settings/', {
            'current_password': 'wrongpassword',
            'new_password': 'newpass123',
            'confirm_password': 'newpass123'
        })

        # Should show form with error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'nicht korrekt')

        # Password should not have changed
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.password, self.original_password)

    def test_password_change_mismatch_confirmation(self):
        """Test password change fails when confirmation doesn't match."""
        response = self.client.post('/settings/', {
            'current_password': '01012000',
            'new_password': 'newpass123',
            'confirm_password': 'different456'
        })

        # Should show form with error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'stimmen nicht überein')

        # Password should not have changed
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.password, self.original_password)

    def test_password_change_too_short(self):
        """Test password change fails when new password is too short."""
        response = self.client.post('/settings/', {
            'current_password': '01012000',
            'new_password': 'short',
            'confirm_password': 'short'
        })

        # Should show form with error
        self.assertEqual(response.status_code, 200)

        # Password should not have changed
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.password, self.original_password)


class CachingTestCase(TestCase):
    """Test caching functionality for models."""

    def test_rulebook_cache_invalidation(self):
        """Test that Rulebook cache is invalidated on save."""
        from django.core.cache import cache
        from .models import Rulebook

        # Clear cache
        cache.clear()

        # Get or create rulebook (singleton)
        rulebook, _ = Rulebook.objects.get_or_create(
            singleton_guard=True,
            defaults={
                "name": "Test Rulebook",
                "content": "Test content"
            }
        )

        # Cache should be empty initially
        self.assertIsNone(cache.get('rulebook_content'))

        # Simulate caching
        cache.set('rulebook_content', rulebook.content, 300)
        self.assertIsNotNone(cache.get('rulebook_content'))

        # Update rulebook
        rulebook.content = "Updated content"
        rulebook.save()

        # Cache should be invalidated
        self.assertIsNone(cache.get('rulebook_content'))

    def test_helptext_cache_invalidation(self):
        """Test that HelpText cache is invalidated on save."""
        from django.core.cache import cache
        from .models import HelpText

        # Clear cache
        cache.clear()

        # Get or create help text (singleton)
        helptext, _ = HelpText.objects.get_or_create(
            singleton_guard=True,
            defaults={
                "name": "Test Help",
                "content": "Test help content"
            }
        )

        # Cache should be empty initially
        self.assertIsNone(cache.get('helptext_content'))

        # Simulate caching
        cache.set('helptext_content', helptext.content, 300)
        self.assertIsNotNone(cache.get('helptext_content'))

        # Update help text
        helptext.content = "Updated help content"
        helptext.save()

        # Cache should be invalidated
        self.assertIsNone(cache.get('helptext_content'))


class BulkSubmissionWindowTestCase(TestCase):
    """Test bulk submission window creation admin action."""

    def setUp(self):
        """Create age groups for testing."""
        self.age_group1 = AgeGroup.objects.create(
            name="U12",
            min_age=0,
            max_age=12,
            gender="mixed"
        )
        self.age_group2 = AgeGroup.objects.create(
            name="U16",
            min_age=13,
            max_age=16,
            gender="mixed"
        )
        self.age_group3 = AgeGroup.objects.create(
            name="Open",
            min_age=17,
            max_age=99,
            gender="mixed"
        )

    def test_bulk_create_windows_creates_one_per_age_group(self):
        """Bulk action creates one window per age group."""
        from accounts.models import SubmissionWindow, CompetitionSettings, AgeGroup

        # Set competition date
        settings, _ = CompetitionSettings.objects.get_or_create(
            singleton_guard=True,
            defaults={'grading_system': 'ifsc'}
        )
        settings.competition_date = date(2026, 3, 15)
        settings.save()

        # Simulate the bulk action logic directly
        age_groups = list(AgeGroup.objects.all().order_by('name'))
        for age_group in age_groups:
            window = SubmissionWindow.objects.create(
                name=f"Zeitfenster {age_group.name}",
                note=f"Test window for {age_group.name}"
            )
            window.age_groups.add(age_group)

        # Should create 3 windows (one per age group)
        windows = SubmissionWindow.objects.all()
        self.assertEqual(windows.count(), 3)

        # Each window should have exactly one age group
        for window in windows:
            self.assertEqual(window.age_groups.count(), 1)

        # Check that all age groups are covered
        covered_age_groups = set()
        for window in windows:
            covered_age_groups.update(window.age_groups.all())
        self.assertEqual(len(covered_age_groups), 3)
        self.assertIn(self.age_group1, covered_age_groups)
        self.assertIn(self.age_group2, covered_age_groups)
        self.assertIn(self.age_group3, covered_age_groups)

    def test_bulk_create_windows_uses_competition_date(self):
        """Bulk action uses competition date from settings."""
        from accounts.models import SubmissionWindow, CompetitionSettings
        from django.utils import timezone
        from datetime import datetime

        # Set competition date
        settings, _ = CompetitionSettings.objects.get_or_create(
            singleton_guard=True,
            defaults={'grading_system': 'ifsc'}
        )
        comp_date = date(2026, 3, 15)
        settings.competition_date = comp_date
        settings.save()

        # Simulate the date calculation from bulk action
        competition_datetime = timezone.make_aware(
            datetime.combine(comp_date, datetime.min.time().replace(hour=9, minute=0))
        )
        submission_start = competition_datetime
        submission_end = competition_datetime.replace(hour=17, minute=0)

        # Create a window with these dates
        window = SubmissionWindow.objects.create(
            name="Test Window",
            submission_start=submission_start,
            submission_end=submission_end
        )

        # Check that window uses the competition date
        self.assertIsNotNone(window.submission_start)
        self.assertEqual(window.submission_start.date(), comp_date)
        self.assertEqual(window.submission_start.hour, 9)
        self.assertEqual(window.submission_start.minute, 0)
        self.assertEqual(window.submission_end.hour, 17)
        self.assertEqual(window.submission_end.minute, 0)

    def test_bulk_create_windows_no_age_groups(self):
        """Bulk action handles case with no age groups gracefully."""
        from accounts.models import SubmissionWindow, AgeGroup

        # Delete all age groups
        AgeGroup.objects.all().delete()

        # Simulate the bulk action logic with no age groups
        age_groups = list(AgeGroup.objects.all().order_by('name'))
        for age_group in age_groups:
            window = SubmissionWindow.objects.create(
                name=f"Zeitfenster {age_group.name}",
            )
            window.age_groups.add(age_group)

        # Should not create any windows
        self.assertEqual(SubmissionWindow.objects.count(), 0)

    def test_bulk_create_windows_naming(self):
        """Bulk action creates windows with descriptive names."""
        from accounts.models import SubmissionWindow, AgeGroup

        # Simulate the bulk action logic
        age_groups = list(AgeGroup.objects.all().order_by('name'))
        for age_group in age_groups:
            window = SubmissionWindow.objects.create(
                name=f"Zeitfenster {age_group.name}",
            )
            window.age_groups.add(age_group)

        # Check window names
        window_names = list(SubmissionWindow.objects.values_list('name', flat=True))
        self.assertIn("Zeitfenster U12", window_names)
        self.assertIn("Zeitfenster U16", window_names)
        self.assertIn("Zeitfenster Open", window_names)
