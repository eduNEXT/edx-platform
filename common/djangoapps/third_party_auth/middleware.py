"""Middleware classes for third_party_auth."""


import json
import urllib.parse

import six.moves.urllib.parse
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext as _
from requests import HTTPError
from social_core.exceptions import SocialAuthBaseException
from social_django.middleware import SocialAuthExceptionMiddleware

from common.djangoapps.student.helpers import get_next_url_for_login_page

from . import pipeline, provider


def _get_saml_provider_name(request):
    """
    Try to resolve the human-readable provider name from the SAML RelayState
    that is present in the POST body of /auth/complete/tpa-saml/.

    Returns the provider display name (e.g. "Cartão de Cidadão") or None if
    it cannot be determined.
    """
    try:
        backend = getattr(request, 'backend', None)
        if backend is None:
            return None
        relay_state_str = backend.strategy.request_data().get('RelayState', '')
        relay_state = json.loads(relay_state_str)
        idp_slug = relay_state.get('idp')
        if not idp_slug:
            return None
        # provider_id for SAML providers is "saml-<slug>"
        saml_provider = provider.Registry.get(f'saml-{idp_slug}')
        if saml_provider:
            return saml_provider.name
    except Exception:  # pylint: disable=broad-except
        pass
    return None


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

        # For the account_settings SAML flow, /account/settings is a plain RedirectView
        # that goes to the Account MFE without preserving Django messages. Build the
        # MFE URL directly so the ?duplicate_provider param reaches the frontend.
        # This only applies to the tpa-saml backend; OAuth providers are handled by
        # the existing get_duplicate_provider() path in settings_views.account_settings().
        backend_name = getattr(getattr(request, 'backend', None), 'name', None)
        if (
            auth_entry == pipeline.AUTH_ENTRY_ACCOUNT_SETTINGS
            and isinstance(exception, SocialAuthBaseException)
            and backend_name == 'tpa-saml'
        ):
            account_mfe_url = getattr(settings, 'ACCOUNT_MICROFRONTEND_URL', None)
            if account_mfe_url:
                provider_name = _get_saml_provider_name(request) or backend_name
                redirect_uri = '{}?duplicate_provider={}'.format(
                    account_mfe_url.rstrip('/') + '/',
                    urllib.parse.quote(provider_name, safe=''),
                )

        return redirect_uri

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
