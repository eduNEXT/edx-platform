"""
Tests for third party auth middleware
"""


from unittest import mock

import ddt
from django.contrib.messages.middleware import MessageMiddleware
from django.http import HttpResponse
from django.test.client import RequestFactory
from requests.exceptions import HTTPError
from social_core import exceptions as social_exceptions

from common.djangoapps.student.helpers import get_next_url_for_login_page
from common.djangoapps.third_party_auth import pipeline
from common.djangoapps.third_party_auth.middleware import (
    TPA_ERROR_BACKEND_SESSION_KEY,
    TPA_ERROR_CODE_SESSION_KEY,
    ExceptionMiddleware,
)
from common.djangoapps.third_party_auth.tests.testutil import TestCase
from openedx.core.djangolib.testing.utils import skip_unless_lms


class ThirdPartyAuthMiddlewareTestCase(TestCase):
    """Tests that ExceptionMiddleware is correctly redirected"""

    @skip_unless_lms
    @mock.patch('django.conf.settings.MESSAGE_STORAGE', 'django.contrib.messages.storage.cookie.CookieStorage')
    def test_http_exception_redirection(self):
        """
        Test ExceptionMiddleware is correctly redirected to login page
        when PSA raises HttpError exception.
        """

        request = RequestFactory().get("dummy_url")
        next_url = get_next_url_for_login_page(request)
        login_url = '/login?next=' + next_url
        request.META['HTTP_REFERER'] = 'http://example.com:8000/login'
        exception = HTTPError()
        exception.response = HttpResponse(status=502)

        # Add error message for error in auth pipeline
        MessageMiddleware(get_response=lambda request: None).process_request(request)
        response = ExceptionMiddleware(get_response=lambda request: None).process_exception(
            request, exception
        )
        target_url = response.url

        assert response.status_code == 302
        assert target_url.endswith(login_url)

@ddt.ddt
class TPAErrorSessionTestCase(TestCase):
    """
    Tests that ExceptionMiddleware.get_redirect_uri() correctly saves a
    stable error code in the session for the account_settings flow, so that
    account_settings_redirect_view can later forward it to the Account MFE.
    """

    def _build_request(self, exception, auth_entry=pipeline.AUTH_ENTRY_ACCOUNT_SETTINGS):
        request = RequestFactory().get('/auth/login/tpa-saml/')
        request.session = {}
        request.session[pipeline.AUTH_ENTRY_KEY] = auth_entry

        class FakeBackend:
            name = 'tpa-saml'
        request.backend = FakeBackend()
        request.social_strategy = mock.MagicMock()
        request.social_strategy.setting.return_value = None

        ExceptionMiddleware(get_response=lambda r: None).get_redirect_uri(request, exception)
        return request

    @ddt.data(
        (social_exceptions.AuthAlreadyAssociated, 'duplicate_provider'),
        (social_exceptions.AuthCanceled, 'auth_canceled'),
        (social_exceptions.AuthFailed, 'auth_failed'),
        (social_exceptions.AuthTokenError, 'token_error'),
        (social_exceptions.AuthStateMissing, 'state_missing'),
        (social_exceptions.AuthStateForbidden, 'state_forbidden'),
        (social_exceptions.AuthTokenRevoked, 'token_revoked'),
        (social_exceptions.AuthUnreachableProvider, 'unreachable_provider'),
    )
    @ddt.unpack
    def test_recognized_exception_saves_error_code_in_session(self, exception_class, expected_code):
        request = self._build_request(exception_class('tpa-saml'))

        assert request.session.get(TPA_ERROR_CODE_SESSION_KEY) == expected_code
        assert request.session.get(TPA_ERROR_BACKEND_SESSION_KEY) == 'tpa-saml'

    def test_unrecognized_exception_does_not_touch_session(self):
        request = self._build_request(social_exceptions.InvalidEmail('tpa-saml'))

        assert TPA_ERROR_CODE_SESSION_KEY not in request.session
        assert TPA_ERROR_BACKEND_SESSION_KEY not in request.session

    def test_error_outside_account_settings_entry_does_not_touch_session(self):
        """
        The session should only be populated for the account_settings flow;
        AUTH_DISPATCH_URLS already handles /login and /register correctly
        without needing this extra context.
        """
        request = self._build_request(
            social_exceptions.AuthAlreadyAssociated('tpa-saml'),
            auth_entry=pipeline.AUTH_ENTRY_LOGIN,
        )

        assert TPA_ERROR_CODE_SESSION_KEY not in request.session
        assert TPA_ERROR_BACKEND_SESSION_KEY not in request.session
