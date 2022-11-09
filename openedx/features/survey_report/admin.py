"""
Django Admin page for SurveyReport.
"""


from django.contrib import admin
from .models import SurveyReport

class SurveyReportAdmin(admin.ModelAdmin):
    """
    Admin to manage survey reports.
    """
    change_list_template = "survey_report/change_list.html"

    readonly_fields = (
        'courses_offered', 'learners', 'registered_learners',
        'enrollments', 'generated_certificates', 'extra_data',
        'request_details', 'created_at', 'sent_at'
    )

    list_display = (
        'id', 'created_at', 'sent'
    )

    def sent(self, obj) -> bool:
        """
        Method to display if a report had been sent according to sent_date.
        """
        return obj.sent_at is not None

    def has_add_permission(self, request):
        """
        Removes the "add" button from admin.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """
        Removes the "delete" options from admin.
        """
        return False

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """
        Removes the "save" buttons from admin change view.
        """
        extra_context = extra_context or {}

        extra_context['show_save'] = False
        extra_context['show_save_and_continue'] = False
        extra_context['show_save_and_add_another'] = False

        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_actions(self, request):
        """
        Removes the default bulk delete option provided by Django,
        it doesn't do what we need for this model.
        """
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

admin.site.register(SurveyReport, SurveyReportAdmin)
