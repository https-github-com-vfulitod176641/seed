# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-12-14 03:02
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
from datetime import datetime

from seed.utils.organizations import default_pm_mappings


def snapshot_mappings(ColumnMapping, org):
    # logic adapted from ColumnMapping static method, get_column_mappings
    column_mappings = ColumnMapping.objects.filter(super_organization=org)
    formatted_mappings = []
    for cm in column_mappings:
        if not cm.column_mapped.all().exists():
            continue

        raw_columns_info = cm.column_raw.all().values_list('column_name', flat=True)
        mapped_columns_info = cm.column_mapped.all().values_list('table_name', 'column_name')

        if len(raw_columns_info) != 1:
            print('skipped raw_columns_info: ', raw_columns_info)
            continue

        if len(mapped_columns_info) != 1:
            print('skipped mapped_columns_info: ', mapped_columns_info)
            continue

        raw_col_name = raw_columns_info[0]
        mapped_col = mapped_columns_info[0]

        mapping = {
            "to_field": mapped_col[1],
            "from_field": raw_col_name,
            "from_units": None,
            "to_table_name": mapped_col[0],
        }

        # check there are no duplicates
        formatted_mappings.append(mapping)

    return formatted_mappings


def forwards(apps, schema_editor):
    Organization = apps.get_model("orgs", "Organization")
    ColumnMapping = apps.get_model("seed", "ColumnMapping")

    todays_date = datetime.date(datetime.now()).isoformat()

    for org in Organization.objects.all():
        if org.column_mappings.exists():
            # Create mappings based on snapshot of current org mappings
            snapshot_mapping_name = todays_date + ' org-wide mapping snapshot'
            org.columnmappingpreset_set.create(
                name=snapshot_mapping_name,
                mappings=snapshot_mappings(ColumnMapping, org)
            )

        # Create PM mappings
        pm_mapping_name = 'Portfolio Manager Defaults'
        org.columnmappingpreset_set.create(
            name=pm_mapping_name,
            mappings=default_pm_mappings()
        )


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0011_auto_20190714_2159'),
        ('seed', '0116_auto_20191219_1606'),
    ]

    operations = [
        migrations.CreateModel(
            name='ColumnMappingPreset',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('mappings', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=list)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('organizations', models.ManyToManyField(to='orgs.Organization')),
            ],
        ),
        migrations.RunPython(forwards),
    ]