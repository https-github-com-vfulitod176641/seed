# Generated by Django 2.2.10 on 2020-04-13 23:03

from django.db import migrations, models


def forwards(apps, schema_editor):
    Rule = apps.get_model('seed', 'Rule')
    # data_type not null:
    #     data_type is 1:
    #         text_match null: not_null -> not_null;
    #                         !not_null -> required: required;
    #                                   -> !required -> '';
    #         text_match not null: include -> not_null: (+)not_null;
    #                                      -> !not_null -> required: (+)required;
    #     data_type is not 1 (0,2,3,4,5):
    #         min and max null: not_null -> not_null;
    #                         : !not_null -> required: required;
    #                                     -> !required: '';
    #         min or max not null: range -> not_null: (+)not_null;
    #                                    -> !not_null -> (+)required: required;
    # data_type null:
    #     min and max null -> text_match null: not_null -> not_null;
    #                                         !not_null -> required: required;
    #                                                   -> !required: '';
    #                      -> text_match not null: include -> not_null: (+)not_null;
    #                                                      -> !not_null -> required: (+)required;
    #     min or max not null: range -> not_null: (+)not_null;
    #                                -> !not_null -> required: (+)required;

    def create_condition(rule, condition):
        Rule.objects.create(name=rule['name'], description=rule['description'], table_name=rule['table_name'], field=rule['field'],
                            enabled=rule['enabled'], data_type=rule['data_type'], rule_type=rule['rule_type'], min=rule['min'],
                            max=rule['max'], severity=rule['severity'], units=rule['units'],
                            data_quality_check_id=rule['data_quality_check_id'], status_label_id=rule['status_label_id'],
                            text_match=rule['text_match'], condition=condition)

    Rule.objects.filter(data_type=1, text_match=None, not_null=True).update(condition='not_null')
    Rule.objects.filter(data_type=1, text_match=None, required=True, not_null=False).update(condition='required')
    Rule.objects.filter(data_type=1, text_match=None, required=False, not_null=False).update(condition='')
    Rule.objects.filter(data_type=1, text_match='').filter(not_null=True).update(condition='not_null')
    Rule.objects.filter(data_type=1, text_match='').filter(required=True, not_null=False).update(condition='required')
    Rule.objects.filter(data_type=1, text_match='').filter(required=False, not_null=False).update(condition='')
    Rule.objects.filter(data_type=1).exclude(text_match=None).exclude(text_match='').update(condition='include')

    for rule in Rule.objects.filter(data_type=1).exclude(text_match=None).exclude(text_match='').filter(not_null=True).values():
        create_condition(rule, 'not_null')

    for rule in Rule.objects.filter(data_type=1).exclude(text_match=None).exclude(text_match='').filter(required=True, not_null=False).values():
        create_condition(rule, 'required')

    Rule.objects.filter(data_type__in=[0, 2, 3, 4, 5], min=None, max=None, not_null=True).update(condition='not_null')
    Rule.objects.filter(data_type__in=[0, 2, 3, 4, 5], min=None, max=None, required=True, not_null=False).update(condition='required')
    Rule.objects.filter(data_type__in=[0, 2, 3, 4, 5], min=None, max=None, required=False, not_null=False).update(condition='')
    Rule.objects.filter(data_type__in=[0, 2, 3, 4, 5]).exclude(min=None, max=None).update(condition='range')

    for rule in Rule.objects.filter(data_type__in=[0, 2, 3, 4, 5]).exclude(min=None, max=None).filter(not_null=True).values():
        create_condition(rule, 'not_null')

    for rule in Rule.objects.filter(data_type__in=[0, 2, 3, 4, 5]).exclude(min=None, max=None).filter(required=True, not_null=False).values():
        create_condition(rule, 'required')

    Rule.objects.filter(data_type=None, min=None, max=None, text_match=None, not_null=True).update(condition='not_null')
    Rule.objects.filter(data_type=None, min=None, max=None, text_match=None, required=True, not_null=False).update(condition='required')
    Rule.objects.filter(data_type=None, min=None, max=None, text_match=None, required=False, not_null=False).update(condition='')
    Rule.objects.filter(data_type=None, min=None, max=None, text_match='', not_null=True).update(condition='not_null')
    Rule.objects.filter(data_type=None, min=None, max=None, text_match='', required=True, not_null=False).update(condition='required')
    Rule.objects.filter(data_type=None, min=None, max=None, text_match='', required=False, not_null=False).update(condition='')

    Rule.objects.filter(data_type=None).exclude(text_match='').exclude(text_match=None).update(condition='include')
    for rule in Rule.objects.exclude(text_match='').exclude(text_match=None).filter(data_type=None, not_null=True).values():
        create_condition(rule, 'not_null')

    for rule in Rule.objects.exclude(text_match='').exclude(text_match=None).filter(data_type=None, required=True, not_null=False).values():
        create_condition(rule, 'required')

    Rule.objects.filter(data_type=None).exclude(min=None, max=None).update(condition='range')
    for rule in Rule.objects.filter(data_type=None, not_null=True).exclude(min=None, max=None).values():
        create_condition(rule, 'not_null')

    for rule in Rule.objects.filter(data_type=None, required=True, not_null=False).exclude(min=None, max=None).values():
        create_condition(rule, 'required')


class Migration(migrations.Migration):

    dependencies = [
        ('seed', '0124_auto_20200323_1509'),
    ]

    operations = [
        migrations.AddField(
            model_name='rule',
            name='condition',
            field=models.CharField(blank=True, default='', max_length=200),
        ),

        migrations.RunPython(forwards),
    ]
