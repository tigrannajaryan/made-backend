# Generated by Django 2.0.3 on 2018-06-19 07:25

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0032_stylist_has_invited_clients'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stylist',
            name='service_time_gap',
            field=models.DurationField(default=datetime.timedelta(0, 1800)),
        ),
    ]