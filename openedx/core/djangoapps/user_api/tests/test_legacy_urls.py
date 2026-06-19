"""
Tests for account_settings_redirect_view in legacy_urls.py.
"""
from django.test import RequestFactory, TestCase, override_settings

from common.djangoapps.third_party_auth.middleware import (
    TPA_ERROR_BACKEND_SESSION_KEY,
    TPA_ERROR_CODE_SESSION_KEY,
)
from openedx.core.djangoapps.user_api.legacy_urls import account_settings_redirect_view


@override_settings(ACCOUNT_MICROFRONTEND_URL='https://account.example.com')
class AccountSettingsRedirectViewTests(TestCase):
    """
    Tests for the view that replaces the legacy /account/settings
    RedirectView, so that third-party-auth errors saved in the session by
    ExceptionMiddleware are forwarded to the Account MFE as query params.
    """

    def _build_request(self, error_code=None, backend_name=None):
        """Build a fake request with optional TPA error session data."""
        request = RequestFactory().get('/account/settings')
        request.session = {}
        if error_code:
            request.session[TPA_ERROR_CODE_SESSION_KEY] = error_code
        if backend_name:
            request.session[TPA_ERROR_BACKEND_SESSION_KEY] = backend_name
        return request

    def test_redirects_without_params_when_no_error_in_session(self):
        """Redirect to Account MFE without query params when session has no errors."""
        request = self._build_request()

        response = account_settings_redirect_view(request)

        assert response.status_code == 302
        assert response.url == 'https://account.example.com'

    def test_redirects_with_duplicate_provider_param(self):
        """Redirect includes duplicate_provider-specific query param when applicable."""
        request = self._build_request(error_code='duplicate_provider', backend_name='tpa-saml')

        response = account_settings_redirect_view(request)

        assert response.status_code == 302
        assert response.url.startswith('https://account.example.com/?')
        assert 'tpa_error_code=duplicate_provider' in response.url
        assert 'duplicate_provider=' in response.url

    def test_redirects_with_other_error_code_without_duplicate_provider_param(self):
        """
        For error codes other than 'duplicate_provider', only tpa_error_code
        should be sent -- 'duplicate_provider' is specific to the
        AuthAlreadyAssociated case, which is the only one the Account MFE
        currently knows how to render.
        """
        request = self._build_request(error_code='auth_canceled', backend_name='tpa-saml')

        response = account_settings_redirect_view(request)

        assert response.status_code == 302
        assert 'tpa_error_code=auth_canceled' in response.url
        assert 'duplicate_provider' not in response.url

    def test_session_error_keys_are_consumed(self):
        """Ensure TPA error session keys are cleared after redirect."""
        request = self._build_request(error_code='duplicate_provider', backend_name='tpa-saml')

        account_settings_redirect_view(request)

        assert TPA_ERROR_CODE_SESSION_KEY not in request.session
        assert TPA_ERROR_BACKEND_SESSION_KEY not in request.session
