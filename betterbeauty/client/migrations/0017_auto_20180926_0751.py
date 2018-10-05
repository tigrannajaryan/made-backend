# Generated by Django 2.1 on 2018-09-26 11:51

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0016_auto_20180914_0744'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='country',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='client',
            name='location',
            field=django.contrib.gis.db.models.fields.PointField(geography=True, null=True, srid=4326),
        ),
    ]
