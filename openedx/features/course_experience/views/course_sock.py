"""
Fragment for rendering the course's sock and associated toggle button.
"""

from django.template.loader import render_to_string
from opaque_keys.edx.keys import CourseKey
from web_fragments.fragment import Fragment

from lms.djangoapps.courseware.courses import get_course_with_access
from lms.djangoapps.courseware.utils import (
    can_show_verified_upgrade,
    verified_upgrade_deadline_link
)

from openedx.core.djangoapps.plugin_api.views import EdxFragmentView
from openedx.features.discounts.utils import format_strikeout_price
from student.models import CourseEnrollment


class CourseSockFragmentView(EdxFragmentView):
    """
    A fragment to provide extra functionality in a dropdown sock.
    """

    def render_to_fragment(self, request, course=None, course_id=None, **kwargs):
        """
        Render the course's sock fragment.
        """
        if course is None:
            course_key = CourseKey.from_string(course_id)
            course = get_course_with_access(request.user, 'load', course_key)

        context = self.get_verification_context(request, course)
        html = render_to_string('course_experience/course-sock-fragment.html', context)
        return Fragment(html)

    @staticmethod
    def get_verification_context(request, course):
        enrollment = CourseEnrollment.get_enrollment(request.user, course.id)
        show_course_sock = can_show_verified_upgrade(request.user, enrollment, course)
        if show_course_sock:
            upgrade_url = verified_upgrade_deadline_link(request.user, course=course)
            course_price, _ = format_strikeout_price(request.user, course)
        else:
            upgrade_url = ''
            course_price = ''

        context = {
            'show_course_sock': show_course_sock,
            'course_price': course_price,
            'course_id': course.id,
            'upgrade_url': upgrade_url,
        }

        return context
