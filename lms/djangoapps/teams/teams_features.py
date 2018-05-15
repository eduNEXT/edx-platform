import logging

from django.conf import settings
from web_fragments.fragment import Fragment

from courseware.courses import get_course_by_id
from courseware.model_data import FieldDataCache
from courseware.module_render import get_module_for_descriptor
from openedx.core.djangoapps.crawlers.models import CrawlersConfig

from xmodule.x_module import STUDENT_VIEW

CONTENT_DEPTH = 2
SECTION_NAME = getattr(settings, "TEAM_SECTION", "Teams")
LOG = logging.getLogger(__name__)


class ModifyTeams(object):
    """this class alows to modifies the team's behavior"""

    def __init__(self, request, user, course_key):

        self.effective_user = user
        self.course_key = course_key
        self.course = get_course_by_id(self.course_key, CONTENT_DEPTH)
        self._prefetch_and_bind_course(request)

        self.section = self._find_section()
        self.subsection = self._find_subsection()

    def get_fragment(self):
        """This method allows to get a fragment from a course's section"""
        unit = self._find_unit()
        if unit:
            frag = unit.render(STUDENT_VIEW)
            return frag
        return None

    def _find_section(self):
        """
        Finds the section where the rocketChat's unit was defined.
        """
        sections = self.course.get_children()
        for section in sections:
            if section.display_name==SECTION_NAME:
                return section
        LOG.warning("The section, where the rocketChat's unit was defined, is missing")
        return None

    def _find_subsection(self):
        """
        Finds the subsection.
        """
        if self.section:
            subsections = self.section.get_children()
            if len(subsections)==1:
                return subsections[0]
            else:
                LOG.warning("Only one subsection must be defined")
        return None

    def _find_unit(self):
        """
        Finds the rocketchat's unit.
        """
        if self.subsection:
            units = self.subsection.get_children()
            if len(units)==1:
                return units[0]
            else:
                LOG.warning("Only one unit must be defined")
        return None

    def _prefetch_and_bind_course(self, request):
        """
        Prefetches all descendant data for the requested section and
        sets up the runtime, which binds the request user to the section.
        """
        self.field_data_cache = FieldDataCache.cache_for_descriptor_descendents(
            self.course_key,
            self.effective_user,
            self.course,
            depth=CONTENT_DEPTH,
            read_only=CrawlersConfig.is_crawler(request),
        )
        self.course = get_module_for_descriptor(
            self.effective_user,
            request,
            self.course,
            self.field_data_cache,
            self.course_key,
            course=self.course,
        )

    def discussion_is_available(self):
        """
        This method checks if teams are using discussion
        """
        if "discussion_is_available" in self.course.teams_configuration:
            return self.course.teams_configuration["discussion_is_available"]
        return True
