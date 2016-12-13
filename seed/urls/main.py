# !/usr/bin/env python
# encoding: utf-8
"""
:copyright (c) 2014 - 2016, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Department of Energy) and contributors. All rights reserved.  # NOQA
:author
"""

from django.conf.urls import url

from seed.views.main import (
    home, create_pm_mapping,
    get_total_number_of_buildings_for_user,         # TO REMOVE
    get_building,                                   # TO REMOVE
    search_buildings,                               # TO REMOVE
    get_default_columns,
    set_default_columns,
    get_default_building_detail_columns,
    set_default_building_detail_columns,
    get_columns,
    save_match,
    get_match_tree,
    get_coparents,
    get_PM_filter_by_counts,
    delete_duplicates_from_import_file,
    delete_file,
    remap_buildings,
    public_search, export_buildings,
    export_buildings_progress,
    export_buildings_download,
    angular_js_tests,
    delete_organization_buildings,
    delete_organization_inventory,
    delete_buildings
)
from seed.views.properties import (
    create_cycle,
    get_cycles,
    update_cycle,
    delete_cycle
)

# prefix, to revert back to original endpoints, leave this blank
apiv1 = r''  # r'api/v1/'

urlpatterns = [

    # cycle routes
    url(r'^' + apiv1 + r'create_cycle/$', create_cycle, name='create_cycle'),
    url(r'^' + apiv1 + r'get_cycles/$', get_cycles, name='get_cycles'),
    url(r'^' + apiv1 + r'update_cycle/$', update_cycle, name='update_cycle'),
    url(r'^' + apiv1 + r'delete_cycle/$', delete_cycle, name='delete_cycle'),

    # template routes
    url(r'^$', home, name='home'),

    url(r'^' + apiv1 + r'create_pm_mapping/$', create_pm_mapping,
        name='create_pm_mapping'),

    # TO REMOVE
    url(
        r'^' + apiv1 + r'get_total_number_of_buildings_for_user/$',
        get_total_number_of_buildings_for_user,
        name='get_total_number_of_buildings_for_user'
    ),
    url(r'^' + apiv1 + r'get_building/$', get_building, name='get_building'),
    url(r'^' + apiv1 + r'search_buildings/$', search_buildings,
        name='search_buildings'),
    url(
        r'^' + apiv1 + r'get_default_columns/$',
        get_default_columns,
        name='get_default_columns'
    ),
    url(
        r'^' + apiv1 + r'set_default_columns/$',
        set_default_columns,
        name='set_default_columns'
    ),
    url(
        r'^' + apiv1 + r'get_default_building_detail_columns/$',
        get_default_building_detail_columns,
        name='get_default_building_detail_columns'
    ),
    url(
        r'^' + apiv1 + r'set_default_building_detail_columns/$',
        set_default_building_detail_columns,
        name='set_default_building_detail_columns'
    ),
    url(r'^' + apiv1 + r'get_columns/$', get_columns, name='get_columns'),
    url(r'^' + apiv1 + r'save_match/$', save_match, name='save_match'),
    url(r'^' + apiv1 + r'get_match_tree/$', get_match_tree,
        name='get_match_tree'),
    url(r'^' + apiv1 + r'get_coparents/$', get_coparents,
        name='get_coparents'),
    url(
        r'^' + apiv1 + r'get_PM_filter_by_counts/$',
        get_PM_filter_by_counts,
        name='get_PM_filter_by_counts'
    ),
    url(
        r'^' + apiv1 + r'delete_duplicates_from_import_file/$',
        delete_duplicates_from_import_file,
        name='delete_duplicates_from_import_file',
    ),
    url(r'^' + apiv1 + r'delete_file/$', delete_file, name='delete_file'),
    # url(r'^' + apiv1 + r'update_building/$', update_building,
    #     name='update_building'),

    # Building reports
    # url(
    #     r'^' + apiv1 + r'get_building_summary_report_data/$',
    #     get_building_summary_report_data,
    #     name='get_building_summary_report_data',
    # ),
    # url(
    #     r'^' + apiv1 + r'get_building_report_data/$',
    #     get_building_report_data,
    #     name='get_building_report_data',
    # ),
    # url(
    #     r'^' + apiv1 + r'get_aggregated_building_report_data/$',
    #     get_aggregated_building_report_data,
    #     name='get_aggregated_building_report_data',
    # ),

    # New MCM endpoints
    url(r'^' + apiv1 + r'remap_buildings/$', remap_buildings,
        name='remap_buildings'),
    url(
        r'^' + apiv1 + r'public_search/$',
        public_search,
        name='public_search'
    ),

    # exporter routes
    url(r'^' + apiv1 + r'export_buildings/$', export_buildings,
        name='export_buildings'),
    url(
        r'^' + apiv1 + r'export_buildings/progress/$',
        export_buildings_progress,
        name='export_buildings_progress'
    ),
    url(
        r'^' + apiv1 + r'export_buildings/download/$',
        export_buildings_download,
        name='export_buildings_download'
    ),

    # test URLs
    url(r'^angular_js_tests/$', angular_js_tests, name='angular_js_tests'),

    # org
    url(
        r'^' + apiv1 + r'delete_organization_buildings/$',
        delete_organization_buildings,
        name='delete_organization_buildings'
    ),
    url(
        r'^' + apiv1 + r'delete_organization_inventory/$',
        delete_organization_inventory,
        name='delete_organization_inventory'
    ),

    # delete
    url(
        r'^' + apiv1 + r'delete_buildings/$',
        delete_buildings,
        name='delete_buildings'
    ),

]
