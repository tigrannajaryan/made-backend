# Generated by Django 2.1 on 2018-10-26 17:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0061_salon_country_from_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='salon',
            name='public_phone',
            field=models.CharField(default=None, max_length=20, null=True, unique=True),
        ),
    ]