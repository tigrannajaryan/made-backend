# Generated by Django 2.1 on 2019-02-20 07:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0013_notification_twilio_message_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='sms_message',
            field=models.CharField(blank=True, default=None, max_length=1024, null=True),
        ),
    ]