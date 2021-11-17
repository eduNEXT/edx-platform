"""
Test that various filters are fired for models in the student app.
"""
from unittest import mock
import pytest

from django.db.utils import IntegrityError
from django.test import TestCase
from django_countries.fields import Country

from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.tests.factories import UserFactory, UserProfileFactory

from openedx.core.djangolib.testing.utils import skip_unless_lms
from django.test import TestCase, override_settings
from openedx_filters.learning.enrollment import PreEnrollmentFilter


from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from openedx_filters import PipelineStep

class TestEnrollmentPipelineStep(PipelineStep):
    """
    Utility function used when getting steps for pipeline.
    """

    def do_filter(self, user, course_key, mode):
        """Pipeline steps that changes mode to honor."""
        if mode == "no-id-professional":
            raise PreEnrollmentFilter.PreventEnrollment()
        return {"mode": "honor"}


@skip_unless_lms
class EnrollmentFiltersTest(ModuleStoreTestCase):
    """
    Tests for the Open edX Events associated with the enrollment process through the enroll method.

    This class guarantees that the following events are sent during the user's enrollment, with
    the exact Data Attributes as the event definition stated:
    """

    def setUp(self):  # pylint: disable=arguments-differ
        super().setUp()
        self.course = CourseFactory.create()
        self.user = UserFactory.create(
            username="test",
            email="test@example.com",
            password="password",
        )
        self.user_profile = UserProfileFactory.create(user=self.user, name="Test Example")

    @override_settings(
        OPEN_EDX_FILTERS_CONFIG={
            "org.openedx.learning.course.enrollment.started.v1": {
                "pipeline": [
                    "common.djangoapps.student.tests.test_filters.TestEnrollmentPipelineStep",
                ],
                "fail_silently": False,
            },
        },
    )
    def test_enrollment_filter_executed(self):
        """
        Test whether the student enrollment event is sent after the user's
        enrollment process.

        Expected result:
            - COURSE_ENROLLMENT_CREATED is sent and received by the mocked receiver.
            - The arguments that the receiver gets are the arguments sent by the event
            except the metadata generated on the fly.
        """
        enrollment = CourseEnrollment.enroll(self.user, self.course.id, mode='audit')

        self.assertEqual('honor', enrollment.mode)

    @override_settings(
        OPEN_EDX_FILTERS_CONFIG={
            "org.openedx.learning.course.enrollment.started.v1": {
                "pipeline": [
                    "common.djangoapps.student.tests.test_filters.TestEnrollmentPipelineStep",
                ],
                "fail_silently": False,
            },
        },
    )
    def test_enrollment_filter_prevent_enroll(self):
        """
        Test whether the student enrollment event is sent after the user's
        enrollment process.

        Expected result:
            - COURSE_ENROLLMENT_CREATED is sent and received by the mocked receiver.
            - The arguments that the receiver gets are the arguments sent by the event
            except the metadata generated on the fly.
        """
        with self.assertRaises(PreEnrollmentFilter.PreventEnrollment):
            CourseEnrollment.enroll(self.user, self.course.id, mode='no-id-professional')
