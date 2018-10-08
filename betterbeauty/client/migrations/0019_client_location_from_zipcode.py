# Generated by Django 2.1 on 2018-09-26 12:44

from django.contrib.gis.db.backends.postgis.schema import PostGISSchemaEditor
from django.db import migrations
from django.db.migrations.state import StateApps


from integrations.gmaps import GeoCode


def set_location_from_zipcode(apps: StateApps, schema_editor: PostGISSchemaEditor):
    Client = apps.get_model('client', 'Client')
    clients = Client.objects.filter(location=None)
    for client in clients:
        geo_coded_address = GeoCode(client.zip_code).geo_code(country=client.country)
        if geo_coded_address:
            client.location = geo_coded_address.location
            client.save()


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0018_client_country_from_phone'),
    ]

    operations = [
        migrations.RunPython(code=set_location_from_zipcode, reverse_code=migrations.RunPython.noop)
    ]
