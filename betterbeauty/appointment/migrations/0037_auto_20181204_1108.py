# Generated by Django 2.1 on 2018-12-04 16:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0007_auto_20181115_1213'),
        ('appointment', '0036_auto_20181127_0602'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='stylist_new_appointment_notification',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to='notifications.Notification'),
        ),
        migrations.AddField(
            model_name='appointment',
            name='stylist_new_appointment_notification_sent_at',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
