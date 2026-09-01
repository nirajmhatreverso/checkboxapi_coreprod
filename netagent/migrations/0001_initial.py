"""
Initial migration for netagent app.

IMPORTANT: All three models use managed = False, meaning Django will NOT
create or alter the tables in Oracle (they already exist).

This migration file exists purely so that:
  1. `migrate` does not complain about missing migrations.
  2. If you later set managed = True (e.g. for a dev SQLite database),
     Django can scaffold the schema automatically.

To generate a fresh migration after any model change run:
    python manage.py makemigrations netagent
"""

from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # No DDL operations — tables are unmanaged (managed = False).
        # Django respects the existing Oracle schema as-is.
    ]