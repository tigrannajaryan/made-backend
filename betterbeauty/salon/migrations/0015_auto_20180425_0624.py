import uuid

from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0014_auto_20180425_0624'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servicetemplateset',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='servicecategory',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='servicetemplate',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='templates',
                                    to='salon.ServiceCategory'),
        ),
        migrations.AlterField(
            model_name='servicetemplate',
            name='templateset',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='templates',
                                    to='salon.ServiceTemplateSet'),
        ),
        migrations.AlterField(
            model_name='servicetemplateset',
            name='name',
            field=models.CharField(max_length=255, unique=True),
        ),

    ]
