"""
CLI command to generate survey report.
"""

from django.core.management.base import BaseCommand, CommandError
from openedx.features.survey_report.application import generate_report

class Command(BaseCommand):
    """
    Command to generate survey report.
    """

    help = 'This command will generate survey report.'

    def handle(self, *args, **options):
        try:
            generate_report()
        except Exception as error:
            raise CommandError('An error has ocurred while report was generating.') from error

        self.stdout.write(self.style.SUCCESS('Survey report has been generated successfully.'))
