from django.db import migrations


def forwards(apps, schema_editor):
    schema_editor.execute(
        "DO $$"
        "BEGIN"
        "  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname = 'readonly_user') THEN"
        "    GRANT SELECT ON ALL SEQUENCES IN SCHEMA public, information_schema, pg_catalog TO readonly_user;"
        "  END IF;"
        "END $$;"
    )


def backwards(apps, schema_editor):
    schema_editor.execute(
        "DO $$"
        "BEGIN"
        "  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname = 'readonly_user') THEN"
        "    REVOKE SELECT ON ALL SEQUENCES IN SCHEMA public, information_schema, pg_catalog FROM readonly_user;"
        "  END IF;"
        "END $$;"
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_set_env_password_for_readonly'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards)
    ]
