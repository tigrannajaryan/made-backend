# Generated by Django 2.1 on 2019-02-07 23:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('appointment', '0045_appointment_stylist_payout_fee'),
    ]

    operations = [
        migrations.RenameField(
            model_name='appointment',
            old_name='stylist_payout_fee',
            new_name='stylist_payout_amount',
        ),
    ]
