"""Imports every model module so Alembic autogenerate and the app see all tables.

Add one line here whenever a new models module is created. A forgotten line is caught by the
"models and migrations agree" test, because the table would look like drift.
"""

import app.core.auth.models  # noqa: F401
