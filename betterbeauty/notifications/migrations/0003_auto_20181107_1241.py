# Generated by Django 2.1 on 2018-11-07 17:41

import django.contrib.postgres.fields.jsonb
from django.db import migrations
import notifications.models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_notification_channel'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=notifications.models.default_json_field_value),
        ),
    ]
