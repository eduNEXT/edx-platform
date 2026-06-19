"""
Defines the URL routes for this app.
"""
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.urls import include, path, re_path
from rest_framework import routers

from common.djangoapps.third_party_auth import provider
from common.djangoapps.third_party_auth.middleware import (
    TPA_ERROR_BACKEND_SESSION_KEY,
    TPA_ERROR_CODE_SESSION_KEY,
)
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers

from . import views as user_api_views
from .models import UserPreference

USER_API_ROUTER = routers.DefaultRouter()
USER_API_ROUTER.register(r'users', user_api_views.UserViewSet)
USER_API_ROUTER.register(r'user_prefs', user_api_views.UserPreferenceViewSet)

def account_settings_redirect_view(request):
    """
    Backward-compatible redirect for /account and /account/settings to the
    Account MFE.

    Unlike a plain RedirectView, this reads third-party-auth error info from
    the session (set by ExceptionMiddleware.get_redirect_uri) and forwards it
    to the MFE as query params, instead of dropping it.

    Only 'duplicate_provider' is currently rendered by the MFE
    (AuthAlreadyAssociated). Other error codes are sent via 'tpa_error_code'
    for forward-compatibility.
    """
    account_mfe_url = configuration_helpers.get_value(
        'ACCOUNT_MICROFRONTEND_URL',
        settings.ACCOUNT_MICROFRONTEND_URL,
    ).rstrip('/')

    error_code = request.session.pop(TPA_ERROR_CODE_SESSION_KEY, None)
    backend_name = request.session.pop(TPA_ERROR_BACKEND_SESSION_KEY, None)

    if not error_code:
        return redirect(account_mfe_url)

    params = {'tpa_error_code': error_code}

    if error_code == 'duplicate_provider' and backend_name:
        enabled_providers = list(provider.Registry.get_enabled_by_backend_name(backend_name))
        params['duplicate_provider'] = enabled_providers[0].name if enabled_providers else backend_name

    return redirect(f'{account_mfe_url}/?{urlencode(params)}')

urlpatterns = [
    # This redirect is needed for backward compatibility with the old URL structure for the authentication
    # workflows using third-party authentication providers until the authentication workflows fully support
    # the URL structure with MFEs.
    re_path(r'^account(?:/settings)?/?$', account_settings_redirect_view),
    path('user_api/v1/', include(USER_API_ROUTER.urls)),
    re_path(
        fr'^user_api/v1/preferences/(?P<pref_key>{UserPreference.KEY_REGEX})/users/$',
        user_api_views.PreferenceUsersListView.as_view()
    ),
    re_path(
        r'^user_api/v1/forum_roles/(?P<name>[a-zA-Z]+)/users/$',
        user_api_views.ForumRoleUsersListView.as_view()
    ),

    path('user_api/v1/preferences/email_opt_in/', user_api_views.UpdateEmailOptInPreference.as_view(),
         name="preferences_email_opt_in_legacy"
         ),
    path('user_api/v1/preferences/time_zones/', user_api_views.CountryTimeZoneListView.as_view(),
         ),
]
