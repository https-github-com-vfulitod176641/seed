"""
:copyright (c) 2014 - 2020, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Department of Energy) and contributors. All rights reserved.  # NOQA
:author
"""
from collections import namedtuple

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.db.models import Subquery
from django.http import JsonResponse
from drf_yasg.utils import no_body, swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from seed.data_importer.utils import usage_point_id
from seed.decorators import ajax_request_class
from seed.lib.superperms.orgs.decorators import has_perm_class
from seed.lib.superperms.orgs.models import Organization
from seed.models import (AUDIT_USER_EDIT, DATA_STATE_MATCHING,
                         MERGE_STATE_DELETE, MERGE_STATE_MERGED,
                         MERGE_STATE_NEW, VIEW_LIST, VIEW_LIST_PROPERTY,
                         Column, ColumnListSetting, ColumnListSettingColumn,
                         Cycle, Meter, Note, Property, PropertyAuditLog,
                         PropertyMeasure, PropertyState, PropertyView,
                         Simulation)
from seed.models import StatusLabel as Label
from seed.models import TaxLotProperty, TaxLotView
from seed.serializers.pint import (PintJSONEncoder,
                                   apply_display_unit_preferences)
from seed.serializers.properties import (PropertySerializer,
                                         PropertyStateSerializer,
                                         PropertyViewSerializer,
                                         UpdatePropertyPayloadSerializer)
from seed.serializers.taxlots import TaxLotViewSerializer
from seed.utils.api import OrgMixin, ProfileIdMixin, api_endpoint_class
from seed.utils.api_schema import (AutoSchemaHelper,
                                   swagger_auto_schema_org_query_param)
from seed.utils.labels import get_labels
from seed.utils.match import match_merge_link
from seed.utils.merge import merge_properties
from seed.utils.meters import PropertyMeterReadingsExporter
from seed.utils.properties import (get_changed_fields,
                                   pair_unpair_property_taxlot,
                                   properties_across_cycles,
                                   update_result_with_master)

# Global toggle that controls whether or not to display the raw extra
# data fields in the columns returned for the view.
DISPLAY_RAW_EXTRADATA = True
DISPLAY_RAW_EXTRADATA_TIME = True

ErrorState = namedtuple('ErrorState', ['status_code', 'message'])


class PropertyViewSet(viewsets.ViewSet, OrgMixin, ProfileIdMixin):
    renderer_classes = (JSONRenderer,)
    parser_classes = (JSONParser,)
    serializer_class = PropertySerializer
    _organization = None

    def _get_filtered_results(self, request, profile_id):
        page = request.query_params.get('page', 1)
        per_page = request.query_params.get('per_page', 1)
        org_id = request.query_params.get('organization_id', None)
        cycle_id = request.query_params.get('cycle')
        # check if there is a query paramater for the profile_id. If so, then use that one
        profile_id = request.query_params.get('profile_id', profile_id)

        if not org_id:
            return JsonResponse(
                {'status': 'error', 'message': 'Need to pass organization_id as query parameter'},
                status=status.HTTP_400_BAD_REQUEST)

        if cycle_id:
            cycle = Cycle.objects.get(organization_id=org_id, pk=cycle_id)
        else:
            cycle = Cycle.objects.filter(organization_id=org_id).order_by('name')
            if cycle:
                cycle = cycle.first()
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Could not locate cycle',
                    'pagination': {
                        'total': 0
                    },
                    'cycle_id': None,
                    'results': []
                })

        # Return property views limited to the 'property_view_ids' list. Otherwise, if selected is empty, return all
        if 'property_view_ids' in request.data and request.data['property_view_ids']:
            property_views_list = PropertyView.objects.select_related('property', 'state', 'cycle') \
                .filter(id__in=request.data['property_view_ids'],
                        property__organization_id=org_id, cycle=cycle) \
                .order_by('id')  # TODO: test adding .only(*fields['PropertyState'])
        else:
            property_views_list = PropertyView.objects.select_related('property', 'state', 'cycle') \
                .filter(property__organization_id=org_id, cycle=cycle) \
                .order_by('id')  # TODO: test adding .only(*fields['PropertyState'])

        paginator = Paginator(property_views_list, per_page)

        try:
            property_views = paginator.page(page)
            page = int(page)
        except PageNotAnInteger:
            property_views = paginator.page(1)
            page = 1
        except EmptyPage:
            property_views = paginator.page(paginator.num_pages)
            page = paginator.num_pages

        org = Organization.objects.get(pk=org_id)

        # Retrieve all the columns that are in the db for this organization
        columns_from_database = Column.retrieve_all(org_id, 'property', False)

        # This uses an old method of returning the show_columns. There is a new method that
        # is prefered in v2.1 API with the ProfileIdMixin.
        if profile_id is None:
            show_columns = None
        elif profile_id == -1:
            show_columns = list(Column.objects.filter(
                organization_id=org_id
            ).values_list('id', flat=True))
        else:
            try:
                profile = ColumnListSetting.objects.get(
                    organization=org,
                    id=profile_id,
                    settings_location=VIEW_LIST,
                    inventory_type=VIEW_LIST_PROPERTY
                )
                show_columns = list(ColumnListSettingColumn.objects.filter(
                    column_list_setting_id=profile.id
                ).values_list('column_id', flat=True))
            except ColumnListSetting.DoesNotExist:
                show_columns = None

        related_results = TaxLotProperty.get_related(property_views, show_columns,
                                                     columns_from_database)

        # collapse units here so we're only doing the last page; we're already a
        # realized list by now and not a lazy queryset
        unit_collapsed_results = [apply_display_unit_preferences(org, x) for x in related_results]

        response = {
            'pagination': {
                'page': page,
                'start': paginator.page(page).start_index(),
                'end': paginator.page(page).end_index(),
                'num_pages': paginator.num_pages,
                'has_next': paginator.page(page).has_next(),
                'has_previous': paginator.page(page).has_previous(),
                'total': paginator.count
            },
            'cycle_id': cycle.id,
            'results': unit_collapsed_results
        }

        return JsonResponse(response)

    def _move_relationships(self, old_state, new_state):
        """
        In general, we move the old relationships to the new state since the old state should not be
        accessible anymore. If we ever unmerge, then we need to decide who gets the data.. both?

        :param old_state: PropertyState
        :param new_state: PropertyState
        :return: PropertyState, updated new_state
        """
        for s in old_state.scenarios.all():
            s.property_state = new_state
            s.save()

        # Move the measures to the new state
        for m in PropertyMeasure.objects.filter(property_state=old_state):
            m.property_state = new_state
            m.save()

        # Move the old building file to the new state to preserve the history
        for b in old_state.building_files.all():
            b.property_state = new_state
            b.save()

        for s in Simulation.objects.filter(property_state=old_state):
            s.property_state = new_state
            s.save()

        return new_state

    @swagger_auto_schema(
        manual_parameters=[AutoSchemaHelper.query_org_id_field(required=True)],
        request_body=AutoSchemaHelper.schema_factory(
            {
                'selected': ['integer'],
            },
            description='IDs for properties to be checked for which labels are applied.'
        )
    )
    @has_perm_class('can_modify_data')
    @action(detail=False, methods=['POST'])
    def labels(self, request):
        """
        Returns a list of all labels where the is_applied field
        in the response pertains to the labels applied to property_view
        """
        labels = Label.objects.filter(
            super_organization=self.get_parent_org(self.request)
        ).order_by("name").distinct()
        super_organization = self.get_organization(request)
        # TODO: refactor to avoid passing request here
        return get_labels(request, labels, super_organization, 'property_view')

    @swagger_auto_schema(
        request_body=AutoSchemaHelper.schema_factory(
            {
                'interval': 'string',
                'excluded_meter_ids': ['integer'],
            },
            required=['property_view_id', 'interval', 'excluded_meter_ids'],
            description='Properties:\n'
                        '- interval: one of "Exact", "Month", or "Year"\n'
                        '- excluded_meter_ids: array of meter IDs to exclude'
        )
    )
    @ajax_request_class
    @has_perm_class('requires_member')
    @action(detail=True, methods=['POST'])
    def meter_usage(self, request, pk):
        """
        Retrieves meter usage information
        """
        body = dict(request.data)
        interval = body['interval']
        excluded_meter_ids = body['excluded_meter_ids']

        property_view = PropertyView.objects.get(pk=pk)
        property_id = property_view.property.id
        org_id = property_view.cycle.organization_id
        scenario_ids = [s.id for s in property_view.state.scenarios.all()]

        exporter = PropertyMeterReadingsExporter(property_id, org_id, excluded_meter_ids, scenario_ids=scenario_ids)

        return exporter.readings_and_column_defs(interval)

    @ajax_request_class
    @has_perm_class('requires_member')
    @action(detail=True, methods=['GET'])
    def meters(self, request, pk):
        """
        Retrieves meters for the property
        """
        property_view = PropertyView.objects.get(pk=pk)
        property_id = property_view.property.id
        scenario_ids = [s.id for s in property_view.state.scenarios.all()]
        energy_types = dict(Meter.ENERGY_TYPES)

        res = []
        for meter in Meter.objects.filter(Q(property_id=property_id) | Q(scenario_id__in=scenario_ids)):
            if meter.source == meter.GREENBUTTON:
                source = 'GB'
                source_id = usage_point_id(meter.source_id)
            elif meter.source == meter.BUILDINGSYNC:
                source = 'BS'
                source_id = meter.source_id
            else:
                source = 'PM'
                source_id = meter.source_id

            res.append({
                'id': meter.id,
                'type': energy_types[meter.type],
                'source': source,
                'source_id': source_id,
                'scenario_id': meter.scenario.id if meter.scenario is not None else None,
                'scenario_name': meter.scenario.name if meter.scenario is not None else None
            })

        return res

    @swagger_auto_schema(
        manual_parameters=[
            AutoSchemaHelper.query_org_id_field(),
            AutoSchemaHelper.query_integer_field(
                'cycle',
                required=False,
                description='The ID of the cycle to get properties'
            ),
            AutoSchemaHelper.query_integer_field(
                'per_page',
                required=False,
                description='Number of properties per page'
            ),
            AutoSchemaHelper.query_integer_field(
                'page',
                required=False,
                description='Page to fetch'
            ),
        ]
    )
    @api_endpoint_class
    @ajax_request_class
    @has_perm_class('requires_viewer')
    def list(self, request):
        """
        List all the properties	with all columns
        """
        return self._get_filtered_results(request, profile_id=-1)

    @swagger_auto_schema(
        request_body=AutoSchemaHelper.schema_factory(
            {
                'organization_id': 'integer',
                'profile_id': 'integer',
                'cycle_ids': ['integer'],
            },
            required=['organization_id', 'cycle_ids'],
            description='Properties:\n'
                        '- organization_id: ID of organization\n'
                        '- profile_id: Either an id of a list settings profile, '
                        'or undefined\n'
                        '- cycle_ids: The IDs of the cycle to get properties'
        )
    )
    @api_endpoint_class
    @ajax_request_class
    @has_perm_class('requires_viewer')
    @action(detail=False, methods=['POST'])
    def filter_by_cycle(self, request):
        """
        List all the properties	with all columns
        """
        # NOTE: we are using a POST http method b/c swagger and django handle
        # arrays differently in query parameters. ie this is just simpler
        org_id = request.data.get('organization_id', None)
        profile_id = request.data.get('profile_id', -1)
        cycle_ids = request.data.get('cycle_ids', [])

        if not org_id:
            return JsonResponse(
                {'status': 'error', 'message': 'Need to pass organization_id as query parameter'},
                status=status.HTTP_400_BAD_REQUEST)

        response = properties_across_cycles(org_id, profile_id, cycle_ids)

        return JsonResponse(response)

    @swagger_auto_schema(
        manual_parameters=[
            AutoSchemaHelper.query_org_id_field(),
            AutoSchemaHelper.query_integer_field(
                'cycle',
                required=False,
                description='The ID of the cycle to get properties'),
            AutoSchemaHelper.query_integer_field(
                'per_page',
                required=False,
                description='Number of properties per page'
            ),
            AutoSchemaHelper.query_integer_field(
                'page',
                required=False,
                description='Page to fetch'
            ),
        ],
        request_body=AutoSchemaHelper.schema_factory(
            {
                'profile_id': 'integer',
                'property_view_ids': ['integer'],
            },
            description='Properties:\n'
                        '- profile_id: Either an id of a list settings profile, or undefined\n'
                        '- property_view_ids: List of property view ids'
        )
    )
    @api_endpoint_class
    @ajax_request_class
    @has_perm_class('requires_viewer')
    @action(detail=False, methods=['POST'])
    def filter(self, request):
        """
        List all the properties
        """
        if 'profile_id' not in request.data:
            profile_id = None
        else:
            if request.data['profile_id'] == 'None':
                profile_id = None
            else:
                profile_id = request.data['profile_id']

                # ensure that profile_id is an int
                try:
                    profile_id = int(profile_id)
                except TypeError:
                    pass

        return self._get_filtered_results(request, profile_id=profile_id)

    @swagger_auto_schema(
        request_body=AutoSchemaHelper.schema_factory(
            {
                'property_view_ids': ['integer']
            },
            required=['property_view_ids'],
            description='Properties:\n'
                        '- property_view_ids: array containing Property view IDs.'
        )
    )
    @api_endpoint_class
    @ajax_request_class
    @action(detail=False, methods=['POST'])
    def meters_exist(self, request):
        """
        Check to see if the given Properties (given by ID) have Meters.
        """
        property_view_ids = request.data.get('property_view_ids', [])
        property_views = PropertyView.objects.filter(
            id__in=property_view_ids
        )
        return Meter.objects.filter(property_id__in=Subquery(property_views.values('property_id'))).exists()

    @swagger_auto_schema(
        manual_parameters=[AutoSchemaHelper.query_org_id_field()],
        request_body=AutoSchemaHelper.schema_factory(
            {
                'property_view_ids': ['integer']
            },
            required=['property_view_ids'],
            description='Array containing property view ids to merge'),
    )
    @api_endpoint_class
    @ajax_request_class
    @has_perm_class('can_modify_data')
    @action(detail=False, methods=['POST'])
    def merge(self, request):
        """
        Merge multiple property records into a single new record, and run this
        new record through a match and merge round within it's current Cycle.
        """
        body = request.data

        property_view_ids = body.get('property_view_ids', [])
        property_state_ids = PropertyView.objects.filter(
            id__in=property_view_ids
        ).values_list('state_id', flat=True)
        organization_id = int(request.query_params.get('organization_id', None))

        # Check the number of state_ids to merge
        if len(property_state_ids) < 2:
            return JsonResponse({
                'status': 'error',
                'message': 'At least two ids are necessary to merge'
            }, status=status.HTTP_400_BAD_REQUEST)

        merged_state = merge_properties(property_state_ids, organization_id, 'Manual Match')

        merge_count, link_count, view_id = match_merge_link(merged_state.propertyview_set.first().id, 'PropertyState')

        result = {
            'status': 'success'
        }

        result.update({
            'match_merged_count': merge_count,
            'match_link_count': link_count,
        })

        return result

    @swagger_auto_schema(
        manual_parameters=[AutoSchemaHelper.query_org_id_field()],
        request_body=no_body,
    )
    @api_endpoint_class
    @ajax_request_class
    @has_perm_class('can_modify_data')
    @action(detail=True, methods=['PUT'])
    def unmerge(self, request, pk=None):
        """
        Unmerge a property view into two property views
        """
        try:
            old_view = PropertyView.objects.select_related(
                'property', 'cycle', 'state'
            ).get(
                id=pk,
                property__organization_id=self.request.GET['organization_id']
            )
        except PropertyView.DoesNotExist:
            return {
                'status': 'error',
                'message': 'property view with id {} does not exist'.format(pk)
            }

        # Duplicate pairing
        paired_view_ids = list(TaxLotProperty.objects.filter(property_view_id=old_view.id)
                               .order_by('taxlot_view_id').values_list('taxlot_view_id', flat=True))

        # Capture previous associated labels
        label_ids = list(old_view.labels.all().values_list('id', flat=True))

        notes = old_view.notes.all()
        for note in notes:
            note.property_view = None

        merged_state = old_view.state
        if merged_state.data_state != DATA_STATE_MATCHING or merged_state.merge_state != MERGE_STATE_MERGED:
            return {
                'status': 'error',
                'message': 'property view with id {} is not a merged property view'.format(pk)
            }

        log = PropertyAuditLog.objects.select_related('parent_state1', 'parent_state2').filter(
            state=merged_state
        ).order_by('-id').first()

        if log.parent_state1 is None or log.parent_state2 is None:
            return {
                'status': 'error',
                'message': 'property view with id {} must have two parent states'.format(pk)
            }

        state1 = log.parent_state1
        state2 = log.parent_state2
        cycle_id = old_view.cycle_id

        # Clone the property record twice, then copy over meters
        old_property = old_view.property
        new_property = old_property
        new_property.id = None
        new_property.save()

        new_property_2 = Property.objects.get(pk=new_property.id)
        new_property_2.id = None
        new_property_2.save()

        Property.objects.get(pk=new_property.id).copy_meters(old_view.property_id)
        Property.objects.get(pk=new_property_2.id).copy_meters(old_view.property_id)

        # If canonical Property is NOT associated to a different -View, delete it
        if not PropertyView.objects.filter(property_id=old_view.property_id).exclude(id=old_view.id).exists():
            Property.objects.get(pk=old_view.property_id).delete()

        # Create the views
        new_view1 = PropertyView(
            cycle_id=cycle_id,
            property_id=new_property.id,
            state=state1
        )
        new_view2 = PropertyView(
            cycle_id=cycle_id,
            property_id=new_property_2.id,
            state=state2
        )

        # Mark the merged state as deleted
        merged_state.merge_state = MERGE_STATE_DELETE
        merged_state.save()

        # Change the merge_state of the individual states
        if log.parent1.name in ['Import Creation',
                                'Manual Edit'] and log.parent1.import_filename is not None:
            # State belongs to a new record
            state1.merge_state = MERGE_STATE_NEW
        else:
            state1.merge_state = MERGE_STATE_MERGED
        if log.parent2.name in ['Import Creation',
                                'Manual Edit'] and log.parent2.import_filename is not None:
            # State belongs to a new record
            state2.merge_state = MERGE_STATE_NEW
        else:
            state2.merge_state = MERGE_STATE_MERGED
        # In most cases data_state will already be 3 (DATA_STATE_MATCHING), but if one of the parents was a
        # de-duplicated record then data_state will be 0. This step ensures that the new states will be 3.
        state1.data_state = DATA_STATE_MATCHING
        state2.data_state = DATA_STATE_MATCHING
        state1.save()
        state2.save()

        # Delete the audit log entry for the merge
        log.delete()

        old_view.delete()
        new_view1.save()
        new_view2.save()

        # Asssociate labels
        label_objs = Label.objects.filter(pk__in=label_ids)
        new_view1.labels.set(label_objs)
        new_view2.labels.set(label_objs)

        # Duplicate notes to the new views
        for note in notes:
            created = note.created
            updated = note.updated
            note.id = None
            note.property_view = new_view1
            note.save()
            ids = [note.id]
            note.id = None
            note.property_view = new_view2
            note.save()
            ids.append(note.id)
            # Correct the created and updated times to match the original note
            Note.objects.filter(id__in=ids).update(created=created, updated=updated)

        for paired_view_id in paired_view_ids:
            TaxLotProperty(primary=True,
                           cycle_id=cycle_id,
                           property_view_id=new_view1.id,
                           taxlot_view_id=paired_view_id).save()
            TaxLotProperty(primary=True,
                           cycle_id=cycle_id,
                           property_view_id=new_view2.id,
                           taxlot_view_id=paired_view_id).save()

        return {
            'status': 'success',
            'view_id': new_view1.id
        }

    @swagger_auto_schema_org_query_param
    @api_endpoint_class
    @ajax_request_class
    @has_perm_class('can_modify_data')
    @action(detail=True, methods=['GET'])
    def links(self, request, pk=None):
        """
        Get property details for each linked property across org cycles
        """
        organization_id = request.GET.get('organization_id', None)
        base_view = PropertyView.objects.select_related('cycle').filter(
            pk=pk,
            cycle__organization_id=organization_id
        )

        if base_view.exists():
            result = {'data': []}

            # Grab extra_data columns to be shown in the results
            all_extra_data_columns = Column.objects.filter(
                organization_id=organization_id,
                is_extra_data=True,
                table_name='PropertyState'
            ).values_list('column_name', flat=True)

            linked_views = PropertyView.objects.select_related('cycle').filter(
                property_id=base_view.get().property_id,
                cycle__organization_id=organization_id
            ).order_by('-cycle__start')
            for linked_view in linked_views:
                state_data = PropertyStateSerializer(
                    linked_view.state,
                    all_extra_data_columns=all_extra_data_columns
                ).data

                state_data['cycle_id'] = linked_view.cycle.id
                state_data['view_id'] = linked_view.id
                result['data'].append(state_data)

            return JsonResponse(result, encoder=PintJSONEncoder, status=status.HTTP_200_OK)
        else:
            result = {
                'status': 'error',
                'message': 'property view with id {} does not exist in given organization'.format(pk)
            }
            return JsonResponse(result)

    @swagger_auto_schema(
        manual_parameters=[AutoSchemaHelper.query_org_id_field()],
        request_body=no_body
    )
    @api_endpoint_class
    @ajax_request_class
    @has_perm_class('can_modify_data')
    @action(detail=True, methods=['POST'])
    def match_merge_link(self, request, pk=None):
        """
        Runs match merge link for an individual property.

        Note that this method can return a view_id of None if the given -View
        was not involved in a merge.
        """
        merge_count, link_count, view_id = match_merge_link(pk, 'PropertyState')

        result = {
            'view_id': view_id,
            'match_merged_count': merge_count,
            'match_link_count': link_count,
        }

        return JsonResponse(result)

    @swagger_auto_schema(
        manual_parameters=[
            AutoSchemaHelper.query_org_id_field(),
            AutoSchemaHelper.query_integer_field(
                'taxlot_id',
                required=True,
                description='The taxlot id to pair up with this property',
            ),
        ],
        request_body=no_body,
    )
    @api_endpoint_class
    @ajax_request_class
    @has_perm_class('can_modify_data')
    @action(detail=True, methods=['PUT'])
    def pair(self, request, pk=None):
        """
        Pair a taxlot to this property
        """
        organization_id = int(request.query_params.get('organization_id'))
        property_id = int(pk)
        taxlot_id = int(request.query_params.get('taxlot_id'))
        return pair_unpair_property_taxlot(property_id, taxlot_id, organization_id, True)

    @swagger_auto_schema(
        manual_parameters=[
            AutoSchemaHelper.query_org_id_field(),
            AutoSchemaHelper.query_integer_field(
                'taxlot_id',
                required=True,
                description='The taxlot id to unpair from this property',
            ),
        ],
        request_body=no_body,
    )
    @api_endpoint_class
    @ajax_request_class
    @has_perm_class('can_modify_data')
    @action(detail=True, methods=['PUT'])
    def unpair(self, request, pk=None):
        """
        Unpair a taxlot from this property
        """
        organization_id = int(request.query_params.get('organization_id'))
        property_id = int(pk)
        taxlot_id = int(request.query_params.get('taxlot_id'))
        return pair_unpair_property_taxlot(property_id, taxlot_id, organization_id, False)

    @swagger_auto_schema(
        manual_parameters=[AutoSchemaHelper.query_org_id_field()],
        request_body=AutoSchemaHelper.schema_factory(
            {
                'property_view_ids': ['integer']
            },
            required=['property_view_ids'],
            description='A list of property view ids to delete')
    )
    @api_endpoint_class
    @ajax_request_class
    @has_perm_class('can_modify_data')
    @action(detail=False, methods=['DELETE'])
    def batch_delete(self, request):
        """
        Batch delete several properties
        """
        property_view_ids = request.data.get('property_view_ids', [])
        property_states = PropertyView.objects.filter(
            id__in=property_view_ids
        )
        resp = PropertyState.objects.filter(pk__in=Subquery(property_states.values('id'))).delete()

        if resp[0] == 0:
            return JsonResponse({'status': 'warning', 'message': 'No action was taken'})

        return JsonResponse({'status': 'success', 'properties': resp[1]['seed.PropertyState']})

    def _get_property_view(self, pk):
        """
        Return the property view

        :param pk: id, The property view ID
        :param cycle_pk: cycle
        :return:
        """
        try:
            property_view = PropertyView.objects.select_related(
                'property', 'cycle', 'state'
            ).get(
                id=pk,
                property__organization_id=self.request.GET['organization_id']
            )
            result = {
                'status': 'success',
                'property_view': property_view
            }
        except PropertyView.DoesNotExist:
            result = {
                'status': 'error',
                'message': 'property view with id {} does not exist'.format(pk)
            }
        return result

    def _get_taxlots(self, pk):
        lot_view_pks = TaxLotProperty.objects.filter(property_view_id=pk).values_list(
            'taxlot_view_id', flat=True)
        lot_views = TaxLotView.objects.filter(pk__in=lot_view_pks).select_related('cycle', 'state').prefetch_related('labels')
        lots = []
        for lot in lot_views:
            lots.append(TaxLotViewSerializer(lot).data)
        return lots

    def get_history(self, property_view):
        """Return history in reverse order"""

        # access the history from the property state
        history, master = property_view.state.history()

        # convert the history and master states to StateSerializers
        master['state'] = PropertyStateSerializer(master['state_data']).data
        del master['state_data']
        del master['state_id']

        for h in history:
            h['state'] = PropertyStateSerializer(h['state_data']).data
            del h['state_data']
            del h['state_id']

        return history, master

    @swagger_auto_schema_org_query_param
    @api_endpoint_class
    @ajax_request_class
    def retrieve(self, request, pk=None):
        """
        Get property details
        """
        result = self._get_property_view(pk)
        if result.get('status', None) != 'error':
            property_view = result.pop('property_view')
            result = {'status': 'success'}
            result.update(PropertyViewSerializer(property_view).data)
            # remove PropertyView id from result
            result.pop('id')

            # Grab extra_data columns to be shown in the result
            organization_id = request.query_params['organization_id']
            all_extra_data_columns = Column.objects.filter(
                organization_id=organization_id,
                is_extra_data=True,
                table_name='PropertyState').values_list('column_name', flat=True)

            result['state'] = PropertyStateSerializer(property_view.state,
                                                      all_extra_data_columns=all_extra_data_columns).data
            result['taxlots'] = self._get_taxlots(property_view.pk)
            result['history'], master = self.get_history(property_view)
            result = update_result_with_master(result, master)
            return JsonResponse(result, encoder=PintJSONEncoder, status=status.HTTP_200_OK)
        else:
            return JsonResponse(result, status=status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(
        manual_parameters=[AutoSchemaHelper.query_org_id_field()],
        request_body=UpdatePropertyPayloadSerializer,
    )
    @api_endpoint_class
    @ajax_request_class
    def update(self, request, pk=None):
        """
        Update a property and run the updated record through a match and merge
        round within it's current Cycle.
        """
        data = request.data

        result = self._get_property_view(pk)
        if result.get('status', None) != 'error':
            property_view = result.pop('property_view')
            property_state_data = PropertyStateSerializer(property_view.state).data

            # get the property state information from the request
            new_property_state_data = data['state']

            # set empty strings to None
            for key, val in new_property_state_data.items():
                if val == '':
                    new_property_state_data[key] = None

            changed_fields, previous_data = get_changed_fields(property_state_data, new_property_state_data)
            if not changed_fields:
                result.update(
                    {'status': 'success', 'message': 'Records are identical'}
                )
                return JsonResponse(result, status=status.HTTP_204_NO_CONTENT)
            else:
                # Not sure why we are going through the pain of logging this all right now... need to
                # reevaluate this.
                log = PropertyAuditLog.objects.select_related().filter(
                    state=property_view.state
                ).order_by('-id').first()

                # if checks above pass, create an exact copy of the current state for historical purposes
                if log.name == 'Import Creation':
                    # Add new state by removing the existing ID.
                    property_state_data.pop('id')
                    # Remove the import_file_id for the first edit of a new record
                    # If the import file has been deleted and this value remains the serializer won't be valid
                    property_state_data.pop('import_file')
                    new_property_state_serializer = PropertyStateSerializer(
                        data=property_state_data
                    )
                    if new_property_state_serializer.is_valid():
                        # create the new property state, and perform an initial save / moving relationships
                        new_state = new_property_state_serializer.save()

                        # Since we are creating a new relationship when we are manually editing the Properties, then
                        # we need to move the relationships over to the new manually edited record.
                        new_state = self._move_relationships(property_view.state, new_state)
                        new_state.save()

                        # then assign this state to the property view and save the whole view
                        property_view.state = new_state
                        property_view.save()

                        PropertyAuditLog.objects.create(organization=log.organization,
                                                        parent1=log,
                                                        parent2=None,
                                                        parent_state1=log.state,
                                                        parent_state2=None,
                                                        state=new_state,
                                                        name='Manual Edit',
                                                        description=None,
                                                        import_filename=log.import_filename,
                                                        record_type=AUDIT_USER_EDIT)

                        result.update(
                            {'state': new_property_state_serializer.data}
                        )

                        # save the property view so that the datetime gets updated on the property.
                        property_view.save()
                    else:
                        result.update({
                            'status': 'error',
                            'message': 'Invalid update data with errors: {}'.format(
                                new_property_state_serializer.errors)}
                        )
                        return JsonResponse(result, encoder=PintJSONEncoder,
                                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)

                # redo assignment of this variable in case this was an initial edit
                property_state_data = PropertyStateSerializer(property_view.state).data

                if 'extra_data' in new_property_state_data:
                    property_state_data['extra_data'].update(
                        new_property_state_data['extra_data']
                    )

                property_state_data.update(
                    {k: v for k, v in new_property_state_data.items() if k != 'extra_data'}
                )

                log = PropertyAuditLog.objects.select_related().filter(
                    state=property_view.state
                ).order_by('-id').first()

                if log.name in ['Manual Edit', 'Manual Match', 'System Match', 'Merge current state in migration']:
                    # Convert this to using the serializer to save the data. This will override the previous values
                    # in the state object.

                    # Note: We should be able to use partial update here and pass in the changed fields instead of the
                    # entire state_data.
                    updated_property_state_serializer = PropertyStateSerializer(
                        property_view.state,
                        data=property_state_data
                    )
                    if updated_property_state_serializer.is_valid():
                        # create the new property state, and perform an initial save / moving
                        # relationships
                        updated_property_state_serializer.save()

                        result.update(
                            {'state': updated_property_state_serializer.data}
                        )

                        # save the property view so that the datetime gets updated on the property.
                        property_view.save()

                        Note.create_from_edit(request.user.id, property_view, new_property_state_data, previous_data)

                        merge_count, link_count, view_id = match_merge_link(property_view.id, 'PropertyState')

                        result.update({
                            'view_id': view_id,
                            'match_merged_count': merge_count,
                            'match_link_count': link_count,
                        })

                        return JsonResponse(result, encoder=PintJSONEncoder,
                                            status=status.HTTP_200_OK)
                    else:
                        result.update({
                            'status': 'error',
                            'message': 'Invalid update data with errors: {}'.format(
                                updated_property_state_serializer.errors)}
                        )
                        return JsonResponse(result, encoder=PintJSONEncoder,
                                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
                else:
                    result = {
                        'status': 'error',
                        'message': 'Unrecognized audit log name: ' + log.name
                    }
                    return JsonResponse(result, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        else:
            return JsonResponse(result, status=status.HTTP_404_NOT_FOUND)


def diffupdate(old, new):
    """Returns lists of fields changed"""
    changed_fields = []
    changed_extra_data = []
    for k, v in new.items():
        if old.get(k, None) != v or k not in old:
            changed_fields.append(k)
    if 'extra_data' in changed_fields:
        changed_fields.remove('extra_data')
        changed_extra_data, _ = diffupdate(old['extra_data'], new['extra_data'])
    return changed_fields, changed_extra_data
