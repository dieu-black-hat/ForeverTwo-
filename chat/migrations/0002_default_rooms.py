"""Creates a "General" room so the app is ready to use right after `migrate`."""
from django.db import migrations


def create_rooms(apps, schema_editor):
    Room = apps.get_model("chat", "Room")
    Room.objects.get_or_create(
        slug="general",
        defaults={"name": "General", "description": "Talk about anything with everyone"},
    )


class Migration(migrations.Migration):
    dependencies = [("chat", "0001_initial")]
    operations = [migrations.RunPython(create_rooms, migrations.RunPython.noop)]
