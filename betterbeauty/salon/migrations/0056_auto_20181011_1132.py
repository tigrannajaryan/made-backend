# Generated by Django 2.1 on 2018-10-11 15:32

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0055_auto_20181010_0755'),
        ('core', '0031_auto_20181011_1126'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='invitation',
            name='created_client',
        ),
        migrations.AlterField(
            model_name='invitation',
            name='created_real_client',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='invitations', to='client.Client'),
        ),
    ]
