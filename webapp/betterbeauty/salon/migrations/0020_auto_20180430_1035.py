from uuid import uuid4

from django.db import migrations


def populate_service_templates_uuids(apps, schema_editor):
    ServiceTemplate = apps.get_model('salon', 'ServiceTemplate')
    for template in ServiceTemplate.objects.all():
        template.uuid = uuid4()
        template.save(update_fields=['uuid', ])


def populate_stylist_service_uuids(apps, schema_editor):
    StylistService = apps.get_model('salon', 'StylistService')
    ServiceTemplate = apps.get_model('salon', 'ServiceTemplate')
    for service in StylistService.all_objects.all():
        try:
            template = ServiceTemplate.objects.get(
                name=service.name,
                description=service.description,
                category=service.category
            )
            service.service_uuid = template.uuid
        except ServiceTemplate.DoesNotExist:
            service.service_uuid = uuid4()
        service.save(update_fields=['service_uuid', ])


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0019_auto_20180430_1035'),
    ]

    operations = [
        migrations.RunPython(populate_service_templates_uuids, migrations.RunPython.noop),
        migrations.RunPython(populate_stylist_service_uuids, migrations.RunPython.noop),
    ]
