#!/usr/bin/env python
"""Django's command-line tool. Run `python manage.py help` to see all commands."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chatproject.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Did you activate your virtual environment "
            "and run `pip install -r requirements.txt`?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
