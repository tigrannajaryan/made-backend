# Generated by Django 2.0.3 on 2018-08-07 12:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0050_auto_20180806_1423'),
    ]

    operations = [
        migrations.AddField(
            model_name='salon',
            name='is_address_geocoded',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='salon',
            name='last_geo_coded',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
