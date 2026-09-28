"""Point the test run at a throwaway database.

Without this the suite writes its fixtures straight into the development
database, so every run leaves stray departments, courses and faculty behind.
The environment variable has to be set before ``app.core.config`` is first
imported, which is why it lives at module scope in conftest.
"""

import os
import pathlib
import tempfile

TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / "smart_college_test.db"
TEST_DB_PATH.unlink(missing_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

# Importing the app registers every model on Base.metadata, so create_all
# below builds the full schema and not just the users table.
from app.main import app  # noqa: E402,F401  (must follow the env var)
from app.core.database import create_db_and_tables  # noqa: E402

create_db_and_tables()
