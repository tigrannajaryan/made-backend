# Generated by Django 2.0.3 on 2018-04-27 10:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0016_servicetemplateset_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='stylistavailableday',
            name='is_available',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='stylistavailableday',
            name='work_end_at',
            field=models.TimeField(null=True),
        ),
        migrations.AddField(
            model_name='stylistavailableday',
            name='work_start_at',
            field=models.TimeField(null=True),
        ),
    ]
