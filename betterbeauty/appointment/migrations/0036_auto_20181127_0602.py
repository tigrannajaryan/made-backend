# Generated by Django 2.1 on 2018-11-27 11:02

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appointment', '0035_auto_20181122_0352'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointment',
            name='client',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='appointments', related_query_name='appointment', to='client.Client'),
        ),
        migrations.AlterField(
            model_name='appointment',
            name='stylist',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='appointments', related_query_name='appointment', to='salon.Stylist'),
        ),
    ]
