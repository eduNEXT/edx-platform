"""Middleware classes for third_party_auth."""


import six.moves.urllib.parse
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext as _
from requests import HTTPError
from social_core import exceptions as social_exceptions
from social_django.middleware import SocialAuthExceptionMiddleware

from common.djangoapps.student.helpers import get_next_url_for_login_page

from . import pipeline

# Maps each social_core exception class to a stable, language-independent
# error code. This is used by account_settings_redirect_view
# (openedx/core/djangoapps/user_api/legacy_urls.py) to forward third-party-auth
# errors to the Account MFE as a query param, since a plain RedirectView does
# not forward Django messages. The Account MFE currently only renders
# 'duplicate_provider' (see frontend-app-account, AccountSettingsPage.jsx);
# the rest are included for forward-compatibility.
TPA_ERROR_CODES = (
    (social_exceptions.AuthAlreadyAssociated, 'duplicate_provider'),
    (social_exceptions.AuthCanceled, 'auth_canceled'),
    (social_exceptions.AuthFailed, 'auth_failed'),
    (social_exceptions.AuthTokenError, 'token_error'),
    (social_exceptions.AuthStateMissing, 'state_missing'),
    (social_exceptions.AuthStateForbidden, 'state_forbidden'),
    (social_exceptions.AuthTokenRevoked, 'token_revoked'),
    (social_exceptions.AuthUnreachableProvider, 'unreachable_provider'),
)

# Session keys used to pass the error code from the middleware to
# account_settings_redirect_view.
TPA_ERROR_CODE_SESSION_KEY = 'tpa_error_code'
TPA_ERROR_BACKEND_SESSION_KEY = 'tpa_error_backend'

class ExceptionMiddleware(SocialAuthExceptionMiddleware, MiddlewareMixin):
    """Custom middleware that handles conditional redirection."""

    def get_redirect_uri(self, request, exception):
        # Fall back to django settings's SOCIAL_AUTH_LOGIN_ERROR_URL.
        redirect_uri = super().get_redirect_uri(request, exception)

        # Safe because it's already been validated by
        # pipeline.parse_query_params. If that pipeline step ever moves later
        # in the pipeline stack, we'd need to validate this value because it
        # would be an injection point for attacker data.
        auth_entry = request.session.get(pipeline.AUTH_ENTRY_KEY)

        # Check if we have an auth entry key we can use instead
        if auth_entry and auth_entry in pipeline.AUTH_DISPATCH_URLS:
            redirect_uri = pipeline.AUTH_DISPATCH_URLS[auth_entry]

        # For the account_settings flow, /account/settings is a plain
        # RedirectView that does not forward Django messages to the Account
        # MFE, so the error would otherwise be silently dropped. Save a
        # stable error code (and backend name) in the session here, while we
        # still have the real exception instance, so
        # account_settings_redirect_view can read it and forward it to the
        # MFE as a query param.
        if auth_entry == pipeline.AUTH_ENTRY_ACCOUNT_SETTINGS:
            self._save_tpa_error_in_session(request, exception)

        return redirect_uri

    @staticmethod
    def _save_tpa_error_in_session(request, exception):
        """
        Stores a stable error code for `exception` in the session, along with
        the backend name, if `exception` is a recognized third-party-auth
        error. No-ops otherwise.
        """
        for exc_class, code in TPA_ERROR_CODES:
            if isinstance(exception, exc_class):
                request.session[TPA_ERROR_CODE_SESSION_KEY] = code
                backend = getattr(request, 'backend', None)
                request.session[TPA_ERROR_BACKEND_SESSION_KEY] = getattr(backend, 'name', None)
                break

    def process_exception(self, request, exception):
        """Handles specific exception raised by Python Social Auth eg HTTPError."""

        referer_url = request.META.get('HTTP_REFERER', '')
        if (referer_url and isinstance(exception, HTTPError) and
                exception.response.status_code == 502):
            referer_url = six.moves.urllib.parse.urlparse(referer_url).path
            if referer_url == reverse('signin_user'):
                messages.error(request, _('Unable to connect with the external provider, please try again'),
                               extra_tags='social-auth')

                redirect_url = get_next_url_for_login_page(request)
                return redirect('/login?next=' + redirect_url)

        return super().process_exception(request, exception)
