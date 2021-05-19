"""Test with pact for eox-tagging API."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application, RefreshToken
from oauth2_provider.settings import oauth2_settings

from common.djangoapps.student.models import UserSignupSource
from eox_tagging.constants import AccessLevel
from eox_tagging.models import Tag

User = get_user_model()

def provider_state(name, **params):  # pylint: disable=unused-argument
    """Common state for pact verification,
    this method sets the necessary conditions to verify the pact contracts.

    https://github.com/reecetech/pactman#provider-states-using-pytest
    """
    target_user = User.objects.create(
        username='staff',
        email='staff@example.com',
    )
    owner_user = User.objects.get(
        username='admin',
    )
    content_type = ContentType.objects.get_for_model(User)
    user_permission, _ = Permission.objects.get_or_create(
                codename='can_call_eox_tagging',
                name='Can access eox-tagging API',
                content_type=content_type,
            )
    owner_user.user_permissions.add(user_permission)
    Tag.objects.create_tag(
        tag_type="subscription_level_user",
        target_object=target_user,
        owner_object=owner_user,
        access=AccessLevel.PUBLIC,
    )


def test_pacts(live_server, pact_verifier):
    """Verify contracts."""
    extra_headers = get_autorization_header()

    pact_verifier.verify(live_server.url, provider_state, extra_headers)


def get_autorization_header():
    """Since all the request need an authorization header in order to avoid a 401, this method
    generates a token for an user and returns the respective authorization header.
    """
    owner_user = User.objects.create(
        username='admin',
        email='admin@example.com',
        is_staff=True,
    )
    application = Application.objects.create()
    expires = timezone.now() + timedelta(seconds=oauth2_settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    access_token = AccessToken(
        user=owner_user,
        scope='',
        expires=expires,
        token="1234",
        application=application
    )
    access_token.save()
    refresh_token = RefreshToken(
        user=owner_user,
        token="5678",
        application=application,
        access_token=access_token
    )
    refresh_token.save()
    return {'Authorization': 'Bearer {}'.format(access_token.token)}
