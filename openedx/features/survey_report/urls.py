"""
Defines URLs for Survey Report.
"""

from django.urls import path
from .views import SurveyReportView

urlpatterns = [
    path('generate', SurveyReportView.as_view(),
         name='openedx.generate_survey_report',
    ),
]
