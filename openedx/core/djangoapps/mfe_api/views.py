from rest_framework.response import Response
from rest_framework.views import APIView

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


class MFEConfigView(APIView):
    """
    Provides an API endpoint for MFE config from site configurations.
    """

    def get(self, request):
        """
        GET /api/mfe/v1/config

        **GET Response Values**
        ```
        {
            "logo": "logo.png",
        }
        ```
        """

        mfe_config = configuration_helpers.get_value('MFE_CONFIG',{})
        return Response(mfe_config)
