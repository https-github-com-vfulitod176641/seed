# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-04-15 18:15
from __future__ import unicode_literals

import django.db.models.deletion
import quantityfield.fields
from django.contrib.postgres.operations import CreateExtension
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('seed', '0101_auto_20190318_1835'),
    ]

    operations = [
        migrations.CreateModel(
            name='MeterReading',
            fields=[
                ('start_time',
                 models.DateTimeField(db_index=True, primary_key=True, serialize=False)),
                ('end_time', models.DateTimeField(db_index=True)),
                ('reading', quantityfield.fields.QuantityField(base_units='kBtu')),
                ('source_unit', models.CharField(blank=True, max_length=255, null=True)),
                ('conversion_factor', models.FloatField(blank=True, null=True)),
            ],
        ),
        migrations.AlterIndexTogether(
            name='timeseries',
            index_together=set([]),
        ),
        migrations.RemoveField(
            model_name='timeseries',
            name='meter',
        ),
        migrations.RemoveField(
            model_name='meter',
            name='energy_type',
        ),
        migrations.RemoveField(
            model_name='meter',
            name='energy_units',
        ),
        migrations.RemoveField(
            model_name='meter',
            name='name',
        ),
        migrations.RemoveField(
            model_name='meter',
            name='property_view',
        ),
        migrations.RemoveField(
            model_name='meter',
            name='scenario',
        ),
        migrations.AddField(
            model_name='meter',
            name='is_virtual',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='meter',
            name='property',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.CASCADE,
                                    related_name='meters', to='seed.Property'),
        ),
        migrations.AddField(
            model_name='meter',
            name='source',
            field=models.IntegerField(
                choices=[(1, 'Portfolio Manager'), (2, 'GreenButton'), (3, 'BuildingSync')],
                default=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='meter',
            name='source_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='meter',
            name='type',
            field=models.IntegerField(
                choices=[(1, 'Coal (anthracite)'), (2, 'Coal (bituminous)'), (3, 'Coke'),
                         (4, 'Diesel'), (5, 'District Chilled Water'), (6, 'District Hot Water'),
                         (7, 'District Steam'), (8, 'Electricity'),
                         (9, 'Electricity - on site renewable'), (10, 'Fuel Oil (No. 1)'),
                         (11, 'Fuel Oil (No. 2)'), (12, 'Fuel Oil (No. 4)'),
                         (13, 'Fuel Oil (No. 5 & No. 6)'), (14, 'Kerosene'), (15, 'Natural Gas'),
                         (16, 'Other'), (17, 'Propane and Liquid Propane'), (18, 'Wood')],
                default=None),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='columnmapping',
            name='source_type',
            field=models.IntegerField(blank=True, choices=[(0, 'Assessed Raw'), (2, 'Assessed'),
                                                           (1, 'Portfolio Raw'), (3, 'Portfolio'),
                                                           (4, 'BuildingSnapshot')], null=True),
        ),
        migrations.DeleteModel(
            name='TimeSeries',
        ),
        migrations.AddField(
            model_name='meterreading',
            name='meter',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.CASCADE,
                                    related_name='meter_readings', to='seed.Meter'),
        ),
        CreateExtension('timescaledb'),
        migrations.RunSQL("ALTER TABLE seed_meterreading DROP CONSTRAINT seed_meterreading_pkey"),
        migrations.RunSQL("SELECT create_hypertable('seed_meterreading', 'start_time');"),
        migrations.AlterUniqueTogether(
            name='meterreading',
            unique_together=set([('meter', 'start_time', 'end_time')]),
        ),
    ]
