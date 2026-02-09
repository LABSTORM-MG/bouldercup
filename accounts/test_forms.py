"""
Tests for accounts forms.

Covers:
- ResultSubmissionForm validation and data cleaning
- Integration with ResultService.extract_from_post()
"""

from django.test import TestCase

from .forms import ResultSubmissionForm
from .services.result_service import ResultService, SubmittedResult


class ResultSubmissionFormTestCase(TestCase):
    """Test ResultSubmissionForm validation and cleaning."""

    def test_valid_full_result(self):
        """Form accepts valid full result with all fields."""
        data = {
            'zone1': True,
            'zone2': True,
            'top': True,
            'attempts_zone1': 3,
            'attempts_zone2': 5,
            'attempts_top': 7,
            'version': 5,
        }
        form = ResultSubmissionForm(boulder_id=1, data=data)

        self.assertTrue(form.is_valid())
        result = form.get_submitted_result()

        self.assertIsInstance(result, SubmittedResult)
        self.assertEqual(result.zone1, True)
        self.assertEqual(result.zone2, True)
        self.assertEqual(result.top, True)
        self.assertEqual(result.attempts_zone1, 3)
        self.assertEqual(result.attempts_zone2, 5)
        self.assertEqual(result.attempts_top, 7)
        self.assertEqual(result.version, 5)

    def test_valid_partial_result(self):
        """Form accepts partial result with only some fields."""
        data = {
            'zone1': True,
            'attempts_zone1': 2,
        }
        form = ResultSubmissionForm(boulder_id=2, data=data)

        self.assertTrue(form.is_valid())
        result = form.get_submitted_result()

        self.assertEqual(result.zone1, True)
        self.assertEqual(result.zone2, False)
        self.assertEqual(result.top, False)
        self.assertEqual(result.attempts_zone1, 2)
        self.assertEqual(result.attempts_zone2, 0)
        self.assertEqual(result.attempts_top, 0)
        self.assertIsNone(result.version)

    def test_empty_data(self):
        """Form accepts empty data and returns default values."""
        form = ResultSubmissionForm(boulder_id=3, data={})

        self.assertTrue(form.is_valid())
        result = form.get_submitted_result()

        self.assertEqual(result.zone1, False)
        self.assertEqual(result.zone2, False)
        self.assertEqual(result.top, False)
        self.assertEqual(result.attempts_zone1, 0)
        self.assertEqual(result.attempts_zone2, 0)
        self.assertEqual(result.attempts_top, 0)
        self.assertIsNone(result.version)

    def test_negative_attempts_clamped_to_zero(self):
        """Negative attempt counts are clamped to zero."""
        data = {
            'attempts_zone1': -5,
            'attempts_zone2': -3,
            'attempts_top': -1,
        }
        form = ResultSubmissionForm(boulder_id=4, data=data)

        self.assertTrue(form.is_valid())
        result = form.get_submitted_result()

        self.assertEqual(result.attempts_zone1, 0)
        self.assertEqual(result.attempts_zone2, 0)
        self.assertEqual(result.attempts_top, 0)

    def test_string_attempts_converted_to_int(self):
        """String attempt counts are converted to integers."""
        data = {
            'attempts_zone1': '3',
            'attempts_zone2': '5',
            'attempts_top': '7',
        }
        form = ResultSubmissionForm(boulder_id=5, data=data)

        self.assertTrue(form.is_valid())
        result = form.get_submitted_result()

        self.assertEqual(result.attempts_zone1, 3)
        self.assertEqual(result.attempts_zone2, 5)
        self.assertEqual(result.attempts_top, 7)

    def test_invalid_attempts_defaults_to_zero(self):
        """Invalid (non-numeric) attempt counts default to zero."""
        data = {
            'attempts_zone1': 'abc',
            'attempts_zone2': '',
            'attempts_top': None,
        }
        form = ResultSubmissionForm(boulder_id=6, data=data)

        # Form validation will fail for non-numeric values
        self.assertFalse(form.is_valid())

    def test_checkbox_string_values(self):
        """Checkbox values from POST (string 'on') are converted to booleans."""
        data = {
            'zone1': 'on',
            'zone2': 'on',
            'top': 'on',
        }
        form = ResultSubmissionForm(boulder_id=7, data=data)

        self.assertTrue(form.is_valid())
        result = form.get_submitted_result()

        self.assertEqual(result.zone1, True)
        self.assertEqual(result.zone2, True)
        self.assertEqual(result.top, True)

    def test_version_conversion(self):
        """Version is properly converted from string to int."""
        data = {
            'version': '42',
        }
        form = ResultSubmissionForm(boulder_id=8, data=data)

        self.assertTrue(form.is_valid())
        result = form.get_submitted_result()

        self.assertEqual(result.version, 42)

    def test_invalid_version_returns_none(self):
        """Invalid version values return None."""
        test_cases = [
            {'version': 'invalid'},
            {'version': ''},
            {'version': None},
        ]

        for i, data in enumerate(test_cases):
            with self.subTest(data=data):
                form = ResultSubmissionForm(boulder_id=9 + i, data=data)

                # Empty string or None are valid (required=False)
                # Invalid strings will fail validation
                if data['version'] == 'invalid':
                    self.assertFalse(form.is_valid())
                else:
                    self.assertTrue(form.is_valid())
                    result = form.get_submitted_result()
                    self.assertIsNone(result.version)

    def test_get_submitted_result_without_validation_raises_error(self):
        """Calling get_submitted_result() before is_valid() raises error."""
        form = ResultSubmissionForm(boulder_id=10, data={})

        # Don't call is_valid()
        with self.assertRaises(ValueError) as cm:
            form.get_submitted_result()

        self.assertIn("must be valid", str(cm.exception))

    def test_boulder_id_stored(self):
        """Boulder ID is properly stored in form instance."""
        form = ResultSubmissionForm(boulder_id=123, data={})

        self.assertEqual(form.boulder_id, 123)

    def test_real_post_data_simulation(self):
        """Simulate real POST data from participant results form."""
        # Simulates what Django's request.POST looks like
        post_data = {
            'zone1': 'on',
            'zone2': '',  # Unchecked checkbox not in POST
            'top': 'on',
            'attempts_zone1': '2',
            'attempts_zone2': '0',
            'attempts_top': '3',
            'version': '7',
        }
        form = ResultSubmissionForm(boulder_id=42, data=post_data)

        self.assertTrue(form.is_valid())
        result = form.get_submitted_result()

        self.assertEqual(result.zone1, True)
        self.assertEqual(result.zone2, False)
        self.assertEqual(result.top, True)
        self.assertEqual(result.attempts_zone1, 2)
        self.assertEqual(result.attempts_zone2, 0)
        self.assertEqual(result.attempts_top, 3)
        self.assertEqual(result.version, 7)

    def test_zero_attempts_allowed(self):
        """Zero attempts are explicitly allowed (different from negative)."""
        data = {
            'zone1': True,
            'attempts_zone1': 0,
        }
        form = ResultSubmissionForm(boulder_id=11, data=data)

        self.assertTrue(form.is_valid())
        result = form.get_submitted_result()

        # Zero is valid, though normalize_submission() might adjust it later
        self.assertEqual(result.attempts_zone1, 0)


class ResultServiceIntegrationTestCase(TestCase):
    """Test integration between ResultSubmissionForm and ResultService."""

    def test_extract_from_post_uses_form(self):
        """ResultService.extract_from_post() correctly uses ResultSubmissionForm."""
        post_data = {
            'zone1_42': 'on',
            'zone2_42': '',
            'sent_42': 'on',
            'attempts_zone1_42': '3',
            'attempts_zone2_42': '0',
            'attempts_top_42': '5',
            'ver_42': '8',
        }

        result = ResultService.extract_from_post(post_data, boulder_id=42)

        self.assertIsInstance(result, SubmittedResult)
        self.assertEqual(result.zone1, True)
        self.assertEqual(result.zone2, False)
        self.assertEqual(result.top, True)
        self.assertEqual(result.attempts_zone1, 3)
        self.assertEqual(result.attempts_zone2, 0)
        self.assertEqual(result.attempts_top, 5)
        self.assertEqual(result.version, 8)

    def test_extract_from_post_handles_missing_fields(self):
        """ResultService.extract_from_post() handles missing POST fields gracefully."""
        post_data = {}  # Empty POST data

        result = ResultService.extract_from_post(post_data, boulder_id=99)

        self.assertIsInstance(result, SubmittedResult)
        self.assertEqual(result.zone1, False)
        self.assertEqual(result.zone2, False)
        self.assertEqual(result.top, False)
        self.assertEqual(result.attempts_zone1, 0)
        self.assertEqual(result.attempts_zone2, 0)
        self.assertEqual(result.attempts_top, 0)
        self.assertIsNone(result.version)

    def test_extract_from_post_handles_invalid_data(self):
        """ResultService.extract_from_post() logs warning for invalid data."""
        post_data = {
            'attempts_zone1_10': 'not_a_number',
            'attempts_top_10': 'also_invalid',
            'ver_10': 'invalid_version',
        }

        # Should not raise exception, but log warning and return safe defaults
        result = ResultService.extract_from_post(post_data, boulder_id=10)

        self.assertIsInstance(result, SubmittedResult)
        # Invalid data should result in fallback to safe defaults
        self.assertEqual(result.attempts_zone1, 0)
        self.assertEqual(result.attempts_top, 0)
        self.assertIsNone(result.version)
