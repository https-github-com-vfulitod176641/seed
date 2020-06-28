# Generated by Django 2.2.10 on 2020-05-01 21:24

from django.db import migrations, models

from seed.lib.xml_mapping.mapper import default_buildingsync_preset_mappings


def create_default_bsync_presets(apps, schema_editor):
    """create a default BuildingSync column mapping preset for each organization"""
    Organization = apps.get_model("orgs", "Organization")

    for org in Organization.objects.all():
        bsync_mapping_name = 'BuildingSync v2.0 Defaults'
        org.columnmappingpreset_set.create(
            name=bsync_mapping_name,
            mappings=default_buildingsync_preset_mappings(),
            preset_type=1
        )


class Migration(migrations.Migration):

    dependencies = [
        ('seed', '0125_dq_refactor'),
    ]

    operations = [
        migrations.AddField(
            model_name='columnmappingpreset',
            name='preset_type',
            field=models.IntegerField(choices=[(0, 'Normal'), (1, 'BuildingSync Default'), (2, 'BuildingSync Custom')], default=0),
        ),
        migrations.RunPython(create_default_bsync_presets),
    ]