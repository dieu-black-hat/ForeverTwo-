"""
Creates the admin account (Hustler by default) the first time you run `migrate`.
Nothing happens if a user with that name already exists.
"""
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations


def create_admin(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    username = settings.DEFAULT_ADMIN_USERNAME
    if not username or User.objects.filter(username__iexact=username).exists():
        return
    User.objects.create(
        username=username,
        password=make_password(settings.DEFAULT_ADMIN_PASSWORD),
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0003_profile"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.RunPython(create_admin, migrations.RunPython.noop)]
