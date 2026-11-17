"""
New users now go straight to their chat after logging in (no forced
password change). This clears the old "must change password" flag for
everyone who already had it.
"""
from django.db import migrations


def clear_flags(apps, schema_editor):
    Profile = apps.get_model("chat", "Profile")
    Profile.objects.filter(must_change_password=True).update(must_change_password=False)


class Migration(migrations.Migration):
    dependencies = [("chat", "0007_screenshot_alert")]
    operations = [migrations.RunPython(clear_flags, migrations.RunPython.noop)]
