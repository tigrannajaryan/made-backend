# Generated by Django 2.1 on 2019-01-23 17:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0089_stylistweekdaydiscount_is_deal_of_week'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='invite_target',
            field=models.CharField(choices=[('client', 'Client'), ('stylist', 'Stylist')], default='client', max_length=10),
        ),
    ]