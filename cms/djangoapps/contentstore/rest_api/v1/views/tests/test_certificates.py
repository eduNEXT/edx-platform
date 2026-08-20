"""
Unit tests for the course's certificate.
"""
from django.urls import reverse
from openedx_authz.constants.roles import COURSE_AUDITOR, COURSE_EDITOR, COURSE_STAFF
from rest_framework import status

from cms.djangoapps.contentstore.tests.utils import CourseTestCase
from cms.djangoapps.contentstore.views.tests.test_certificates import HelperMethods
from openedx.core.djangoapps.authz.tests.mixins import CourseAuthoringAuthzTestMixin

from ...mixins import PermissionAccessMixin


class CourseCertificatesViewTest(CourseTestCase, PermissionAccessMixin, HelperMethods):
    """
    Tests for CourseCertificatesView.
    """

    def setUp(self):
        super().setUp()
        self.url = reverse(
            "cms.djangoapps.contentstore:v1:certificates",
            kwargs={"course_id": self.course.id},
        )

    def test_success_response(self):
        """
        Check that endpoint is valid and success response.
        """
        self._add_course_certificates(count=2, signatory_count=2)
        response = self.client.get(self.url)
        response_data = response.data
        self.assertEqual(response.status_code, status.HTTP_200_OK)  # noqa: PT009
        self.assertEqual(len(response_data["certificates"]), 2)  # noqa: PT009
        self.assertEqual(len(response_data["certificates"][0]["signatories"]), 2)  # noqa: PT009
        self.assertEqual(len(response_data["certificates"][1]["signatories"]), 2)  # noqa: PT009
        self.assertEqual(response_data["course_number_override"], self.course.display_coursenumber)  # noqa: PT009
        self.assertEqual(response_data["course_title"], self.course.display_name_with_default)  # noqa: PT009
        self.assertEqual(response_data["course_number"], self.course.number)  # noqa: PT009


class CourseCertificatesAuthzViewTest(
        CourseAuthoringAuthzTestMixin, CourseTestCase, PermissionAccessMixin, HelperMethods
    ):
    """
    Tests for CourseCertificatesView with AuthZ enabled.
    """

    def setUp(self):
        super().setUp()
        self.url = reverse(
            "cms.djangoapps.contentstore:v1:certificates",
            kwargs={"course_id": self.course.id},
        )

    def test_authorized_user_can_access(self):
        """User with COURSE_STAFF role can access."""
        self._add_course_certificates(count=2, signatory_count=2)
        self.add_user_to_role_in_course(self.authorized_user, COURSE_STAFF.external_key, self.course.id)
        resp = self.authorized_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK

    def test_staff_role_has_can_manage_true(self):
        """User with COURSE_STAFF role gets can_manage=True in response."""
        self._add_course_certificates(count=1, signatory_count=1)
        self.add_user_to_role_in_course(self.authorized_user, COURSE_STAFF.external_key, self.course.id)
        resp = self.authorized_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["can_manage"] is True

    def test_editor_can_view_certificates(self):
        """User with COURSE_EDITOR role can view certificates (has view_certificates)."""
        self._add_course_certificates(count=1, signatory_count=1)
        self.add_user_to_role_in_course(self.authorized_user, COURSE_EDITOR.external_key, self.course.id)
        resp = self.authorized_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK

    def test_editor_has_can_manage_false(self):
        """User with COURSE_EDITOR role gets can_manage=False (no manage_certificates)."""
        self._add_course_certificates(count=1, signatory_count=1)
        self.add_user_to_role_in_course(self.authorized_user, COURSE_EDITOR.external_key, self.course.id)
        resp = self.authorized_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["can_manage"] is False

    def test_unauthorized_user_cannot_access(self):
        """User without any role cannot access."""
        self._add_course_certificates(count=1, signatory_count=1)
        resp = self.unauthorized_client.get(self.url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_auditor_can_view_certificates(self):
        """User with COURSE_AUDITOR role can view certificates (has view_certificates)."""
        self._add_course_certificates(count=1, signatory_count=1)
        self.add_user_to_role_in_course(self.authorized_user, COURSE_AUDITOR.external_key, self.course.id)
        resp = self.authorized_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["can_manage"] is False
