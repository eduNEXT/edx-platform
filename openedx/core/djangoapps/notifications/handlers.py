"""
Handlers for notifications
"""
import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction, ProgrammingError
from django.db.models.signals import post_save
from django.dispatch import receiver
from openedx_events.learning.signals import (
    COURSE_ENROLLMENT_CREATED,
    COURSE_NOTIFICATION_REQUESTED,
    COURSE_UNENROLLMENT_COMPLETED,
    USER_NOTIFICATION_REQUESTED
)

from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.notifications.audience_filters import (
    CohortAudienceFilter,
    CourseRoleAudienceFilter,
    EnrollmentAudienceFilter,
    ForumRoleAudienceFilter,
    TeamAudienceFilter
)
from openedx.core.djangoapps.notifications.base_notification import NotificationAppManager, COURSE_NOTIFICATION_TYPES
from openedx.core.djangoapps.notifications.config.waffle import ENABLE_NOTIFICATIONS
from openedx.core.djangoapps.notifications.email import ONE_CLICK_EMAIL_UNSUB_KEY
from openedx.core.djangoapps.notifications.models import CourseNotificationPreference, NotificationPreference
from openedx.core.djangoapps.notifications.tasks import create_notification_preference
from openedx.core.djangoapps.user_api.models import UserPreference

User = get_user_model()
log = logging.getLogger(__name__)

AUDIENCE_FILTER_CLASSES = {
    'discussion_roles': ForumRoleAudienceFilter,
    'course_roles': CourseRoleAudienceFilter,
    'enrollments': EnrollmentAudienceFilter,
    'teams': TeamAudienceFilter,
    'cohorts': CohortAudienceFilter,
}


@receiver(COURSE_ENROLLMENT_CREATED)
def course_enrollment_post_save(signal, sender, enrollment, metadata, **kwargs):
    """
    Watches for post_save signal for creates on the CourseEnrollment table.
    Generate a CourseNotificationPreference if new Enrollment is created
    """
    if ENABLE_NOTIFICATIONS.is_enabled(enrollment.course.course_key):
        try:
            with transaction.atomic():
                email_opt_out = UserPreference.objects.filter(
                    user_id=enrollment.user.id,
                    key=ONE_CLICK_EMAIL_UNSUB_KEY
                ).exists()
                CourseNotificationPreference.objects.create(
                    user_id=enrollment.user.id,
                    course_id=enrollment.course.course_key,
                    notification_preference_config=NotificationAppManager().get_notification_app_preferences(
                        email_opt_out
                    )
                )
        except IntegrityError:
            log.info(f'CourseNotificationPreference already exists for user {enrollment.user.id} '
                     f'and course {enrollment.course.course_key}')


@receiver(post_save, sender=User)
def create_user_account_preferences(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    """
    Initialize user notification preferences when new user is created.
    """
    preferences = []
    if created:
        try:
            with transaction.atomic():
                for name in COURSE_NOTIFICATION_TYPES.keys():
                    preferences.append(create_notification_preference(instance.id, name))
                NotificationPreference.objects.bulk_create(preferences, ignore_conflicts=True)
        except IntegrityError:
            log.info(f'Account-level CourseNotificationPreference already exists for user {instance.id}')
        except ProgrammingError as e:
            # This is here because there is a dependency issue in the migrations where
            # this signal handler tries to run before the NotificationPreference model is created.
            # In reality, this should never be hit because migrations will have already run.
            log.error(f'ProgrammingError encountered while creating user preferences: {e}')


@receiver(COURSE_UNENROLLMENT_COMPLETED)
def on_user_course_unenrollment(enrollment, **kwargs):
    """
    Removes user notification preference when user un-enrolls from the course
    """
    try:
        user_id = enrollment.user.id
        course_key = enrollment.course.course_key
        preference = CourseNotificationPreference.objects.get(user__id=user_id, course_id=course_key)
        preference.delete()
    except ObjectDoesNotExist:
        log.info(f'Notification Preference does not exist for {enrollment.user.pii.username} in {course_key}')


@receiver(USER_NOTIFICATION_REQUESTED)
def generate_user_notifications(signal, sender, notification_data, metadata, **kwargs):
    """
    Watches for USER_NOTIFICATION_REQUESTED signal and calls send_web_notifications task
    """

    from openedx.core.djangoapps.notifications.tasks import send_notifications
    notification_data = notification_data.__dict__
    notification_data['course_key'] = str(notification_data['course_key'])
    send_notifications.delay(**notification_data)


def calculate_course_wide_notification_audience(course_key, audience_filters):
    """
    Calculate the audience for a course-wide notification based on the audience filters
    """
    if not audience_filters:
        active_enrollments = CourseEnrollment.objects.filter(
            course_id=course_key,
            is_active=True
        ).values_list('user_id', flat=True)
        return list(active_enrollments)

    audience_user_ids = []
    for filter_type, filter_values in audience_filters.items():
        if filter_type in AUDIENCE_FILTER_CLASSES.keys():  # lint-amnesty, pylint: disable=consider-iterating-dictionary
            filter_class = AUDIENCE_FILTER_CLASSES.get(filter_type)
            if filter_class:
                filter_instance = filter_class(course_key)
                filtered_users = filter_instance.filter(filter_values)
                audience_user_ids.extend(filtered_users)
        else:
            raise ValueError(f"Invalid audience filter type: {filter_type}")

    return list(set(audience_user_ids))


@receiver(COURSE_NOTIFICATION_REQUESTED)
def generate_course_notifications(signal, sender, course_notification_data, metadata, **kwargs):
    """
    Watches for COURSE_NOTIFICATION_REQUESTED signal and calls send_notifications task
    """

    from openedx.core.djangoapps.notifications.tasks import send_notifications
    course_notification_data = course_notification_data.__dict__
    user_ids = calculate_course_wide_notification_audience(
        str(course_notification_data['course_key']),
        course_notification_data['audience_filters']
    )
    sender_id = course_notification_data.get('content_context', {}).get('sender_id')
    if sender_id in user_ids:
        user_ids.remove(sender_id)

    notification_data = {
        'course_key': str(course_notification_data['course_key']),
        'user_ids': user_ids,
        'context': course_notification_data.get('content_context'),
        'app_name': course_notification_data.get('app_name'),
        'notification_type': course_notification_data.get('notification_type'),
        'content_url': course_notification_data.get('content_url'),
    }

    send_notifications.delay(**notification_data)
