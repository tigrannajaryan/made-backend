# Generated by Django 2.0.3 on 2018-07-09 17:17

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0038_auto_20180702_1359'),
        ('client', '0007_auto_20180706_1327'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='clientofstylist',
            unique_together={('stylist', 'first_name', 'last_name'), ('stylist', 'client'), ('stylist', 'phone')},
        ),
        migrations.AlterUniqueTogether(
            name='preferredstylist',
            unique_together={('stylist', 'client')},
        ),
    ]