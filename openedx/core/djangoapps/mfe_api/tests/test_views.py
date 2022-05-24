"""
Test the MFE API
"""

from unittest.mock import patch

from django.conf import settings
from django.urls import reverse

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.lib.api.test_utils import ApiTestCase


class MFEConfigTestCase(ApiTestCase):
    """
    Test the MFE API
    """
    @patch.dict(settings.FEATURES, {'ENABLE_MFE_CONFIG_API': True})
    def setUp(self):
        self.mfe_config_api_url = reverse('mfe_config_api')
        return super().setUp()

    def test_get_mfe_config(self):
        """Test the get mfe config from MFE API."""
        mfe_config = configuration_helpers.get_value('MFE_CONFIG',{})
        response_json = self.get_json(self.mfe_config_api_url)
        assert response_json == mfe_config
