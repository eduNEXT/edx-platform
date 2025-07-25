"""
Serializers for the notifications API.
"""

from django.core.exceptions import ValidationError
from rest_framework import serializers

from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.notifications.models import (
    CourseNotificationPreference,
    Notification,
    get_additional_notification_channel_settings,
    get_notification_channels
)

from .base_notification import COURSE_NOTIFICATION_APPS, COURSE_NOTIFICATION_TYPES, EmailCadence
from .email.utils import is_notification_type_channel_editable
from .utils import remove_preferences_with_no_access


def add_info_to_notification_config(config_obj):
    """
    Enhances the notification configuration by appending descriptive 'info' to each notification type.

    This function supports two different structures of `config_obj`, depending on the source of the data:
    either from the account preferences API (`AggregatedNotificationPreferences`) or the course preferences
    API (`UserNotificationPreferenceView`).

    Supported input structures:

    1. From account preferences API:
        {
            'notification_app': {
                'notification_types': {
                    'core': { ... },
                    'non-core': { ... }
                }
            }
        }

    2. From course preferences API:
        {
            'notification_preference_config': {
                'notification_app': {
                    'notification_types': {
                        'core': { ... },
                        'non-core': { ... }
                    }
                }
            }
        }

    For each notification type:
    - If the type is 'core', its info is fetched from `COURSE_NOTIFICATION_APPS[notification_app]['core_info']`.
    - For all other types, info is fetched from `COURSE_NOTIFICATION_TYPES[notification_type]['info']`.

    Parameters:
        config_obj (dict): The notification configuration object to enhance.

    Returns:
        dict: The enhanced configuration object with added 'info' fields.
    """

    config = config_obj.get('notification_preference_config', config_obj)
    for notification_app, app_prefs in config.items():
        notification_types = app_prefs.get('notification_types', {})
        for notification_type, type_prefs in notification_types.items():
            if notification_type == "core":
                type_info = COURSE_NOTIFICATION_APPS.get(notification_app, {}).get('core_info', '')
            else:
                type_info = COURSE_NOTIFICATION_TYPES.get(notification_type, {}).get('info', '')
            type_prefs['info'] = type_info
    return config_obj


class CourseOverviewSerializer(serializers.ModelSerializer):
    """
    Serializer for CourseOverview model.
    """

    class Meta:
        model = CourseOverview
        fields = ('id', 'display_name')


class NotificationCourseEnrollmentSerializer(serializers.ModelSerializer):
    """
    Serializer for CourseEnrollment model.
    """
    course = CourseOverviewSerializer()

    class Meta:
        model = CourseEnrollment
        fields = ('course',)


class UserCourseNotificationPreferenceSerializer(serializers.ModelSerializer):
    """
    Serializer for user notification preferences.
    """
    course_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CourseNotificationPreference
        fields = ('id', 'course_name', 'course_id', 'notification_preference_config',)
        read_only_fields = ('id', 'course_name', 'course_id',)
        write_only_fields = ('notification_preference_config',)

    def to_representation(self, instance):
        """
        Override to_representation to add info of all notification types
        """
        preferences = super().to_representation(instance)
        course_id = self.context['course_id']
        user = self.context['user']
        preferences = add_info_to_notification_config(preferences)
        preferences = remove_preferences_with_no_access(preferences, user)
        preferences['notification_preference_config'] = add_non_editable_in_preference(
            preferences.get('notification_preference_config', {})
        )
        return preferences

    def get_course_name(self, obj):
        """
        Returns course name from course id.
        """
        return CourseOverview.get_from_id(obj.course_id).display_name


class UserNotificationPreferenceUpdateSerializer(serializers.Serializer):
    """
    Serializer for user notification preferences update.
    """

    notification_app = serializers.CharField()
    value = serializers.BooleanField(required=False)
    notification_type = serializers.CharField(required=False)
    notification_channel = serializers.CharField(required=False)
    email_cadence = serializers.CharField(required=False)

    def validate(self, attrs):
        """
        Validation for notification preference update form
        """
        notification_app = attrs.get('notification_app')
        notification_type = attrs.get('notification_type')
        notification_channel = attrs.get('notification_channel')
        notification_email_cadence = attrs.get('email_cadence')

        notification_app_config = self.instance.notification_preference_config

        if notification_email_cadence:
            if not notification_type:
                raise ValidationError(
                    'notification_type is required for email_cadence.'
                )
            if EmailCadence.get_email_cadence_value(notification_email_cadence) is None:
                raise ValidationError(
                    f'{attrs.get("value")} is not a valid email cadence.'
                )

        if notification_type and not notification_channel:
            raise ValidationError(
                'notification_channel is required for notification_type.'
            )

        if not notification_app_config.get(notification_app, None):
            raise ValidationError(
                f'{notification_app} is not a valid notification app.'
            )

        if notification_type:
            notification_types = notification_app_config.get(notification_app).get('notification_types')

            if not notification_types.get(notification_type, None):
                raise ValidationError(
                    f'{notification_type} is not a valid notification type.'
                )

        if (
            notification_channel and
            notification_channel not in get_notification_channels()
            and notification_channel not in get_additional_notification_channel_settings()
        ):
            raise ValidationError(
                f'{notification_channel} is not a valid notification channel setting.'
            )

        if notification_app and notification_type and notification_channel:
            if not is_notification_type_channel_editable(
                notification_app,
                notification_type,
                'email' if notification_channel == 'email_cadence' else notification_channel
            ):
                raise ValidationError({
                    'notification_channel': (
                        f'{notification_channel} is not editable for notification type '
                        f'{notification_type}.'
                    )
                })

        return attrs

    def update(self, instance, validated_data):
        """
        Update notification preference config.
        """
        notification_app = validated_data.get('notification_app')
        notification_type = validated_data.get('notification_type')
        notification_channel = validated_data.get('notification_channel')
        value = validated_data.get('value')
        notification_email_cadence = validated_data.get('email_cadence')

        user_notification_preference_config = instance.notification_preference_config

        # Notification email cadence update
        if notification_email_cadence and notification_type:
            user_notification_preference_config[notification_app]['notification_types'][notification_type][
                'email_cadence'] = notification_email_cadence

        # Notification type channel update
        elif notification_type and notification_channel:
            # Update the notification preference for specific notification type
            user_notification_preference_config[
                notification_app]['notification_types'][notification_type][notification_channel] = value

        # Notification app-wide channel update
        elif notification_channel and not notification_type:
            app_prefs = user_notification_preference_config[notification_app]
            for notification_type_name, notification_type_preferences in app_prefs['notification_types'].items():
                non_editable_channels = get_non_editable_channels(notification_app).get(notification_type_name, [])
                if notification_channel not in non_editable_channels:
                    app_prefs['notification_types'][notification_type_name][notification_channel] = value

        # Notification app update
        else:
            # Update the notification preference for notification_app
            user_notification_preference_config[notification_app]['enabled'] = value

        instance.save()
        return instance


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for the Notification model.
    """

    class Meta:
        model = Notification
        fields = (
            'id',
            'app_name',
            'notification_type',
            'content_context',
            'content',
            'content_url',
            'course_id',
            'last_read',
            'last_seen',
            'created',
        )


def validate_email_cadence(email_cadence: str) -> str:
    """
    Validate email cadence value.
    """
    if EmailCadence.get_email_cadence_value(email_cadence) is None:
        raise ValidationError(f'{email_cadence} is not a valid email cadence.')
    return email_cadence


def validate_notification_app(notification_app: str) -> str:
    """
    Validate notification app value.
    """
    if not COURSE_NOTIFICATION_APPS.get(notification_app):
        raise ValidationError(f'{notification_app} is not a valid notification app.')
    return notification_app


def validate_notification_app_enabled(notification_app: str) -> str:
    """
    Validate notification app is enabled.
    """

    if COURSE_NOTIFICATION_APPS.get(notification_app) and COURSE_NOTIFICATION_APPS.get(notification_app)['enabled']:
        return notification_app
    raise ValidationError(f'{notification_app} is not a valid notification app.')


def validate_notification_type(notification_type: str) -> str:
    """
    Validate notification type value.
    """
    if not COURSE_NOTIFICATION_TYPES.get(notification_type):
        raise ValidationError(f'{notification_type} is not a valid notification type.')
    return notification_type


def validate_notification_channel(notification_channel: str) -> str:
    """
    Validate notification channel value.
    """
    valid_channels = set(get_notification_channels()) | set(get_additional_notification_channel_settings())
    if notification_channel not in valid_channels:
        raise ValidationError(f'{notification_channel} is not a valid notification channel setting.')
    return notification_channel


def get_non_editable_channels(app_name):
    """
    Returns a dict of notification: [non-editable channels] for the given app name.
    """
    non_editable = {"core": COURSE_NOTIFICATION_APPS[app_name].get("non_editable", [])}
    for type_name, type_dict in COURSE_NOTIFICATION_TYPES.items():
        if type_dict.get("non_editable") and not type_dict["is_core"]:
            non_editable[type_name] = type_dict["non_editable"]
    return non_editable


def add_non_editable_in_preference(preference):
    """
    Add non_editable preferences to the preference dict
    """
    for app_name, app_dict in preference.items():
        non_editable = {}
        for type_name in app_dict.get('notification_types', {}).keys():
            if type_name == "core":
                non_editable_channels = COURSE_NOTIFICATION_APPS.get(app_name, {}).get('non_editable', [])
            else:
                non_editable_channels = COURSE_NOTIFICATION_TYPES.get(type_name, {}).get('non_editable', [])
            if non_editable_channels:
                non_editable[type_name] = non_editable_channels
        app_dict['non_editable'] = non_editable
    return preference


class UserNotificationPreferenceUpdateAllSerializer(serializers.Serializer):
    """
    Serializer for user notification preferences update with custom field validators.
    """
    notification_app = serializers.CharField(
        required=True,
        validators=[validate_notification_app, validate_notification_app_enabled]
    )
    value = serializers.BooleanField(required=False)
    notification_type = serializers.CharField(
        required=True,
    )
    notification_channel = serializers.CharField(
        required=False,
        validators=[validate_notification_channel]
    )
    email_cadence = serializers.CharField(
        required=False,
        validators=[validate_email_cadence]
    )

    def validate(self, attrs):
        """
        Cross-field validation for notification preference update.
        """
        notification_app = attrs.get('notification_app')
        notification_type = attrs.get('notification_type')
        notification_channel = attrs.get('notification_channel')
        email_cadence = attrs.get('email_cadence')

        # Validate email_cadence requirements
        if email_cadence and not notification_type:
            raise ValidationError({
                'notification_type': 'notification_type is required for email_cadence.'
            })

        # Validate notification_channel requirements
        if not email_cadence and notification_type and not notification_channel:
            raise ValidationError({
                'notification_channel': 'notification_channel is required for notification_type.'
            })

        # Validate notification type
        if all([not COURSE_NOTIFICATION_TYPES.get(notification_type), notification_type != "core"]):
            raise ValidationError(f'{notification_type} is not a valid notification type.')

        # Validate notification type and channel is editable
        if notification_channel and notification_type:
            if not is_notification_type_channel_editable(
                notification_app,
                notification_type,
                "email" if notification_channel == "email_cadence" else notification_channel
            ):
                raise ValidationError({
                    'notification_channel': (
                        f'{notification_channel} is not editable for notification type '
                        f'{notification_type}.'
                    )
                })

        return attrs
