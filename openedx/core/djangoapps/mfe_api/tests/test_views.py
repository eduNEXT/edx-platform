"""
Test the MFE API
"""

from django.conf import settings
from rest_framework import status

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.lib.api.test_utils import ApiTestCase



class MFEConfigTestCase(ApiTestCase):
    """
    Test the MFE API
    """

    def setUp(self):
        self.mfe_config_api_url = '/api/mfe/v1/config'
        return super().setUp()

    def test_get_mfe_config(self):
        """Test the get mfe config from MFE API."""
        response = self.client.get(self.mfe_config_api_url)
        if settings.FEATURES.get('ENABLE_MFE_CONFIG_API'):
            mfe_config = configuration_helpers.get_value('MFE_CONFIG',{})
            response_json = self.get_json(self.mfe_config_api_url)
            assert response_json == mfe_config
        else:
            assert status.HTTP_404_NOT_FOUND == response.status_code
