"""
Default Authentication classes that are ONLY meant to be used by
DEFAULT_AUTHENTICATION_CLASSES for observability purposes.
"""
import jwt
from django.core.cache import cache
from edx_django_utils.monitoring import set_custom_attribute
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed


class DefaultSessionAuthentication(SessionAuthentication):
    """ Default SessionAuthentication with observability """

    def authenticate(self, request):
        # .. custom_attribute_name: using_default_auth_classes
        # .. custom_attribute_description: This custom attribute will always be
        #     True (if not NULL), and signifies that a default authentication
        #     class was used. This can be used to find endpoints using the
        #     default authentication classes.
        set_custom_attribute('using_default_auth_classes', True)

        try:
            user_and_auth = super().authenticate(request)
            if user_and_auth:
                # .. custom_attribute_name: session_auth_result
                # .. custom_attribute_description: The result of session auth, represented
                #      by: 'success', 'failure', or 'n/a'.
                set_custom_attribute('session_auth_result', 'success')
            else:
                set_custom_attribute('session_auth_result', 'n/a')
            return user_and_auth
        except Exception as exception:
            set_custom_attribute('session_auth_result', 'failure')
            raise


class DefaultJwtAuthentication(JwtAuthentication):
    """
    Default JwtAuthentication with observability

    Note that the plan is to add JwtAuthentication as a default, but it
    is not yet used. This class will be used during the transition.
    """

    def authenticate(self, request):
        # .. custom_attribute_name: using_default_auth_classes
        # .. custom_attribute_description: This custom attribute will always be
        #     True (if not NULL), and signifies that a default authentication
        #     class was used. This can be used to find endpoints using the
        #     default authentication classes.
        set_custom_attribute('using_default_auth_classes', True)

        # Unlike the other DRF authentication classes, JwtAuthentication already
        # includes a jwt_auth_result custom attribute, so we do not need to
        # reimplement that observability in this class.
        return super().authenticate(request)


class BlacklistJwtAuthentication(DefaultJwtAuthentication):
    """
    Default JwtAuthentication with Redis-based token revocation support.
    """

    blacklist_key_prefix = 'blacklist:'

    def authenticate(self, request):
        user_and_token = super().authenticate(request)
        if not user_and_token:
            return user_and_token

        user, token = user_and_token
        try:
            claims = jwt.decode(token, options={'verify_signature': False, 'verify_exp': False})
        except jwt.PyJWTError:
            return user, token

        token_subject = claims.get('sub')
        token_issued_at = claims.get('iat')

        if token_subject is None or token_issued_at is None:
            return user, token

        cache_key = f'{self.blacklist_key_prefix}{token_subject}:{token_issued_at}'
        if cache.get(cache_key):
            raise AuthenticationFailed('JWT has been revoked.')

        return user, token
