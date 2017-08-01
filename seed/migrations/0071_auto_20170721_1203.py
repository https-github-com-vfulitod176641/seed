# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2017-07-21 19:03
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seed', '0070_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='propertyview',
            name='cycle',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='seed.Cycle'),
        ),
        migrations.AlterField(
            model_name='taxlotview',
            name='cycle',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='seed.Cycle'),
        ),
    ]