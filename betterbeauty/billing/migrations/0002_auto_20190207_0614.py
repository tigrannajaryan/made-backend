# Generated by Django 2.1 on 2019-02-07 11:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentmethod',
            name='client',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_methods', to='client.Client'),
        ),
    ]
