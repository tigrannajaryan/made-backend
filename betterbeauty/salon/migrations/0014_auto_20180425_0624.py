import datetime
from path import Path
from yaml import load, Loader
import uuid

from django.conf import settings
from django.db import migrations, transaction


def load_templates_from_yaml():
    category_fixtures_path = Path(settings.BASE_DIR) / 'data/service_templates.yaml'
    with open(category_fixtures_path, 'r') as yaml_file:
        data = load(yaml_file, Loader)
    return data


def populate_service_data(apps, schema_editor):

    ServiceTemplateSet = apps.get_model('salon', 'ServiceTemplateSet')
    ServiceCategory = apps.get_model('salon', 'ServiceCategory')
    ServiceTemplate = apps.get_model('salon', 'ServiceTemplate')
    StylistService = apps.get_model('salon', 'StylistService')

    # Delete existing templates and categories. If they are there - they were created
    # for test purposes; they're not supposed to be there anyway

    ServiceTemplate.objects.all().delete()
    StylistService.all_objects.all().delete()
    ServiceTemplateSet.objects.all().delete()

    data = load_templates_from_yaml()
    with transaction.atomic():
        for template_set in data['template_sets']:
            template_set_db, created = ServiceTemplateSet.objects.get_or_create(
                name=template_set['name'],
                sort_weight=template_set['sort_weight'],

            )
            if created:
                template_set_db.uuid = uuid.uuid4()
                template_set_db.save(update_fields=['uuid', ])
            for category in template_set['categories']:
                category_db, created = ServiceCategory.objects.get_or_create(
                    name=category['name']
                )
                if created:
                    category_db.uuid = uuid.uuid4()
                    category_db.save(update_fields=['uuid', ])
                for template in category['templates']:
                    ServiceTemplate.objects.create(
                        category=category_db,
                        templateset=template_set_db,
                        name=template['name'],
                        duration=datetime.timedelta(minutes=template['duration']),
                        base_price=template['base_price']
                    )


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0013_auto_20180425_0624'),
    ]

    operations = [
        migrations.RunPython(populate_service_data, migrations.RunPython.noop),
    ]
