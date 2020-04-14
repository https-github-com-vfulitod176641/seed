# !/usr/bin/env python
# encoding: utf-8
from django.conf.urls import url, include
from rest_framework import routers

from seed.views.v3.data_quality import DataQualityViews
from seed.views.v3.column_list_profiles import ColumnListProfileViews

api_v3_router = routers.DefaultRouter()
api_v3_router.register(r'data_quality_checks', DataQualityViews, base_name='data_quality_checks')
api_v3_router.register(r'column_list_profiles', ColumnListProfileViews, base_name='column_list_profiles')

urlpatterns = [
    url(r'^', include(api_v3_router.urls)),
]
