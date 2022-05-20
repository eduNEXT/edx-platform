""" URL configuration for the mfe API """


from django.conf import settings
from django.urls import path, re_path

from openedx.core.djangoapps.mfe_api.views import MFEConfigView

urlpatterns = [
    re_path(fr'^v1/config', MFEConfigView.as_view(), name='mfe_config_api',)
]
