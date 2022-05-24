""" URL configuration for the mfe API """

from django.urls import re_path

from openedx.core.djangoapps.mfe_api.views import MFEConfigView

urlpatterns = [
    re_path(r'^v1/config', MFEConfigView.as_view(), name='mfe_config_api',)
]
