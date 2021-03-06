# Generated by Django 2.0.3 on 2018-04-17 15:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0004_auto_20180416_1645'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceTemplateSet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('templates', models.ManyToManyField(to='salon.ServiceTemplate')),
                ('sort_weight', models.IntegerField(default=0, verbose_name='Weight in API output; smallest go first'))
            ],
        ),
    ]
