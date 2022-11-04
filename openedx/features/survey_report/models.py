"""
Survey Report models.
"""

from django.db import models
from jsonfield import JSONField

SURVEY_REPORT_PROCESSING = 'processing'
SURVEY_REPORT_GENERATED = 'generated'
SURVEY_REPORT_ERROR = 'error'

SURVEY_REPORT_STATES= [
    (SURVEY_REPORT_PROCESSING, 'Processing'),
    (SURVEY_REPORT_GENERATED, 'Generated'),
    (SURVEY_REPORT_ERROR, 'Error'),
]
class SurveyReport(models.Model):
    """
    This model stores information to automate the way of gathering impact data from the openedx project.

    .. no_pii:
    """
    courses_offered = models.BigIntegerField(default=0)
    learners = models.BigIntegerField(default=0)
    registered_learners = models.BigIntegerField(default=0)
    enrollments = models.BigIntegerField(default=0)
    generated_certificates = models.BigIntegerField(default=0)
    extra_data = JSONField(
        blank=True,
        default=dict,
        help_text="Extra information for instance data",
    )
    created_at = models.DateTimeField(auto_now=True)
    state = models.CharField(
        max_length=24,
        choices=SURVEY_REPORT_STATES,
        default=SURVEY_REPORT_PROCESSING,
    )

    class Meta:
        ordering = ["-created_at"]
        get_latest_by = 'created_at'
