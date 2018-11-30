# Generated by Django 2.1 on 2018-11-29 16:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0073_auto_20181129_0755'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stylist',
            name='google_access_token',
            field=models.CharField(blank=True, default=None, max_length=1024, null=True),
        ),
        migrations.AlterField(
            model_name='stylist',
            name='google_integration_added_at',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name='stylist',
            name='google_refresh_token',
            field=models.CharField(blank=True, default=None, max_length=1024, null=True),
        ),
        migrations.AlterField(
            model_name='stylist',
            name='specialities',
            field=models.ManyToManyField(blank=True, to='salon.Speciality'),
        ),
    ]
