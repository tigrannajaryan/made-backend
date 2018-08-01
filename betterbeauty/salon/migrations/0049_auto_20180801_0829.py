# Generated by Django 2.0.3 on 2018-08-01 12:29

from django.db import migrations
from django.template.defaultfilters import slugify

def set_category_code(apps, schema_editor):
    ServiceCategory = apps.get_model('salon', 'ServiceCategory')
    for service_category in ServiceCategory.objects.all():
        service_category.category_code = slugify(service_category.name)
        service_category.save(update_fields=['category_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0048_servicecategory_category_code'),
    ]

    operations = [
        migrations.RunPython(set_category_code, migrations.RunPython.noop),
    ]
