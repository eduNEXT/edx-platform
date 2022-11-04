"""
Tasks for Survey Report.
"""


import logging

from celery import shared_task
from .api import generate_report
import time

log = logging.getLogger('edx.celery.task')


@shared_task(name='openedx.features.survey_report.tasks.generate_survey_report')
def generate_survey_report():
    """
        clears data_sharing_consent_needed cache for whole enterprise
    """
    log.info(
        'Stated - generate survey report'
    )
    time.sleep(20)
    generate_report()
    log.info('Ended - generate survey report')
