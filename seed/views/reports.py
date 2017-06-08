# !/usr/bin/env python
# encoding: utf-8
"""
:copyright (c) 2014 - 2017, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Department of Energy) and contributors. All rights reserved.  # NOQA
:author
"""
from collections import defaultdict

import dateutil
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from seed.decorators import (
    DecoratorMixin,
)
from seed.models import (
    Cycle,
    PropertyView
)
from seed.utils.api import drf_api_endpoint
from seed.utils.generic import median, round_down_hundred_thousand


class Report(DecoratorMixin(drf_api_endpoint), ViewSet):
    renderer_classes = (JSONRenderer,)
    parser_classes = (JSONParser,)

    def get_cycles(self, start, end):
        organization_id = self.request.GET['organization_id']
        if not isinstance(start, type(end)):
            raise TypeError('start and end not same types')
        # if of type int or convertable  assume they are cycle ids
        try:
            start = int(start)
            end = int(end)
        except ValueError as error:
            # assume string is JS date
            if isinstance(start, basestring):
                start_datetime = dateutil.parser.parse(start)
                end_datetime = dateutil.parser.parse(end)
            else:
                raise error
        # get date times from cycles
        if isinstance(start, int):
            cycle = Cycle.objects.get(pk=start, organization_id=organization_id)
            start_datetime = cycle.start
            if start == end:
                end_datetime = cycle.end
            else:
                end_datetime = Cycle.objects.get(
                    pk=end, organization_id=organization_id
                ).end
        return Cycle.objects.filter(
            start__gte=start_datetime, end__lte=end_datetime,
            organization_id=organization_id
        ).order_by('start')

    def get_data(self, property_view, x_var, y_var):
        result = None
        state = property_view.state
        if getattr(state, x_var, None) and getattr(state, y_var, None):
            result = {
                "id": property_view.property_id,
                "x": getattr(state, x_var),
                "y": getattr(state, y_var),
            }
        return result

    def get_raw_report_data(self, organization_id, cycles, x_var, y_var,
                            campus_only):
        all_property_views = PropertyView.objects.select_related(
            'property', 'state'
        ).filter(
            property__organization_id=organization_id,
            cycle_id__in=cycles
        )
        results = []
        for cycle in cycles:
            property_views = all_property_views.filter(cycle_id=cycle)
            count_total = []
            count_with_data = []
            data = []
            for property_view in property_views:
                property_pk = property_view.property_id
                if property_view.property.campus and campus_only:
                    count_total.append(property_pk)
                    result = self.get_data(property_view, x_var, y_var)
                    if result:
                        result['yr_e'] = cycle.end.strftime('%Y')
                        data.append(result)
                        count_with_data.append(property_pk)
                elif not property_view.property.campus:
                    count_total.append(property_pk)
                    result = self.get_data(property_view, x_var, y_var)
                    if result:
                        result['yr_e'] = cycle.end.strftime('%Y')
                        data.append(result)
                        count_with_data.append(property_pk)
            result = {
                "cycle_id": cycle.pk,
                "chart_data": data,
                "property_counts": {
                    "yr_e": cycle.end.strftime('%Y'),
                    "num_properties": len(count_total),
                    "num_properties_w-data": len(count_with_data),
                },
            }
            results.append(result)
        return results

    def get_property_report_data(self, request):
        campus_only = request.query_params.get('campus_only', False)
        params = {}
        missing_params = []
        error = ''
        valid_values = [
            'site_eui', 'source_eui', 'site_eui_weather_normalized',
            'source_eui_weather_normalized', 'energy_score',
            'gross_floor_area', 'use_description', 'year_built'
        ]
        for param in ['x_var', 'y_var', 'organization_id', 'start', 'end']:
            val = request.query_params.get(param, None)
            if not val:
                missing_params.append(param)
            elif param in ['x_var', 'y_var'] and val not in valid_values:
                error = "{} {} is not a valid value for {}.".format(
                    error, val, param
                )
            else:
                params[param] = val
        if missing_params:
            error = "{} Missing params: {}".format(
                error, ", ".join(missing_params)
            )
        if error:
            status_code = status.HTTP_400_BAD_REQUEST
            result = {'status': 'error', 'message': error}
        else:
            cycles = self.get_cycles(params['start'], params['end'])
            data = self.get_raw_report_data(
                params['organization_id'], cycles,
                params['x_var'], params['y_var'], campus_only
            )
            empty = True
            for datum in data:
                if datum['property_counts']['num_properties_w-data'] != 0:
                    empty = False
                    break
            if empty:
                result = {'status': 'error', 'message': 'No data found'}
                status_code = status.HTTP_404_NOT_FOUND
            else:
                property_counts = []
                chart_data = []
                for datum in data:
                    property_counts.append(datum['property_counts'])
                    chart_data.extend(datum['chart_data'])
                data = {
                    'property_counts': property_counts,
                    'chart_data': chart_data,
                }
                result = {'status': 'success', 'data': data}
                status_code = status.HTTP_200_OK
        return Response(result, status=status_code)

    def get_aggregated_property_report_data(self, request):
        campus_only = request.query_params.get('campus_only', False)
        valid_x_values = [
            'site_eui', 'source_eui', 'site_eui_weather_normalized',
            'source_eui_weather_normalized', 'energy_score',
        ]
        valid_y_values = ['gross_floor_area', 'use_description', 'year_built']
        params = {}
        missing_params = []
        empty = True
        error = ''
        for param in ['x_var', 'y_var', 'organization_id', 'start', 'end']:
            val = request.query_params.get(param, None)
            if not val:
                missing_params.append(param)
            elif param == 'x_var' and val not in valid_x_values:
                error = "{} {} is not a valid value for {}.".format(
                    error, val, param
                )
            elif param == 'y_var' and val not in valid_y_values:
                error = "{} {} is not a valid value for {}.".format(
                    error, val, param
                )
            else:
                params[param] = val
        if missing_params:
            error = "{} Missing params: {}".format(
                error, ", ".join(missing_params)
            )
        if error:
            status_code = status.HTTP_400_BAD_REQUEST
            result = {'status': 'error', 'message': error}
        else:
            cycles = self.get_cycles(params['start'], params['end'])
            x_var = params['x_var']
            y_var = params['y_var']
            data = self.get_raw_report_data(
                params['organization_id'], cycles, x_var, y_var,
                campus_only
            )
            for datum in data:
                if datum['property_counts']['num_properties_w-data'] != 0:
                    empty = False
                    break
            if empty:
                result = {'status': 'error', 'message': 'No data found'}
                status_code = status.HTTP_404_NOT_FOUND
        if not empty or not error:
            chart_data = []
            property_counts = []
            for datum in data:
                buildings = datum['chart_data']
                yr_e = datum['property_counts']['yr_e']
                chart_data.extend(self.aggregate_data(yr_e, y_var, buildings)),
                property_counts.append(datum['property_counts'])
            # Send back to client
            aggregated_data = {
                'chart_data': chart_data,
                'property_counts': property_counts
            }
            result = {
                'status': 'success',
                'aggregated_data': aggregated_data,
            }
            status_code = status.HTTP_200_OK
        return Response(result, status=status_code)

    def aggregate_data(self, yr_e, y_var, buildings):
        aggregation_method = {
            'use_description': self.aggregate_use_description,
            'year_built': self.aggregate_year_built,
            'gross_floor_area': self.aggregate_gross_floor_area,


        }
        return aggregation_method[y_var](yr_e, buildings)

    def aggregate_use_description(self, yr_e, buildings):
        # Group buildings in this year_ending group into uses
        chart_data = []
        grouped_uses = defaultdict(list)
        for b in buildings:
            grouped_uses[str(b['y']).lower()].append(b)

        # Now iterate over use groups to make each chart item
        for use, buildings_in_uses in grouped_uses.items():
            chart_data.append({
                'x': median([b['x'] for b in buildings_in_uses]),
                'y': use.capitalize(),
                'yr_e': yr_e
            })
        return chart_data

    def aggregate_year_built(self, yr_e, buildings):
        # Group buildings in this year_ending group into decades
        chart_data = []
        grouped_decades = defaultdict(list)
        for b in buildings:
            grouped_decades['%s0' % str(b['y'])[:-1]].append(b)

        # Now iterate over decade groups to make each chart item
        for decade, buildings_in_decade in grouped_decades.items():
            chart_data.append({
                'x': median(
                    [b['x'] for b in buildings_in_decade]
                ),
                'y': '%s-%s' % (decade, '%s9' % str(decade)[:-1]),  # 1990-1999
                'yr_e': yr_e
            })
        return chart_data

    def aggregate_gross_floor_area(self, yr_e, buildings):
        chart_data = []
        y_display_map = {
            0: '0-99k',
            100000: '100-199k',
            200000: '200k-299k',
            300000: '300k-399k',
            400000: '400-499k',
            500000: '500-599k',
            600000: '600-699k',
            700000: '700-799k',
            800000: '800-899k',
            900000: '900-999k',
            1000000: 'over 1,000k',
        }
        max_bin = max(y_display_map.keys())

        # Group buildings in this year_ending group into ranges
        grouped_ranges = defaultdict(list)
        for b in buildings:
            area = b['y']
            # make sure anything greater than the biggest bin gets put in
            # the biggest bin
            range_bin = min(max_bin, round_down_hundred_thousand(area))
            grouped_ranges[range_bin].append(b)

        # Now iterate over range groups to make each chart item
        for range_floor, buildings_in_range in grouped_ranges.items():
            chart_data.append({
                'x': median(
                    [b['x'] for b in buildings_in_range]
                ),
                'y': y_display_map[range_floor],
                'yr_e': yr_e
            })
        return chart_data
