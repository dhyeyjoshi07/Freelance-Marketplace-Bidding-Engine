"""
Shared pytest fixtures and configuration for the BidForge test suite.

M-7 fix: Tests that need a live MySQL connection (test_api.py, test_dbms.py)
will be skipped with a helpful message when MySQL is unreachable, instead of
crashing with a raw connection-refused traceback.
"""

import pytest
from sqlalchemy import create_engine, text

TEST_DATABASE_URL = (
    "mysql+pymysql://bidforge_user:bidforge_pass@localhost:3306/bidforge_test"
)


def _mysql_is_reachable() -> bool:
    """Return True if the test MySQL database accepts connections."""
    try:
        engine = create_engine(TEST_DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


# Cache the result so we only probe once per session.
_mysql_ok = _mysql_is_reachable()


def pytest_collection_modifyitems(config, items):
    """
    Auto-skip tests in test_api and test_dbms when MySQL is not running.
    Unit-only suites (test_models, test_match_engine) are unaffected.
    """
    if _mysql_ok:
        return

    skip_mysql = pytest.mark.skip(
        reason=(
            "MySQL is not reachable at localhost:3306.  "
            "Start MySQL and ensure the bidforge_test database exists:\n"
            "  mysql -u root -e \"CREATE DATABASE IF NOT EXISTS bidforge_test;\"\n"
            "  mysql -u root -e \"GRANT ALL ON bidforge_test.* TO 'bidforge_user'@'localhost';\""
        )
    )
    for item in items:
        # Skip any test whose module imports from test_api or test_dbms
        module_name = item.module.__name__
        if "test_api" in module_name or "test_dbms" in module_name:
            item.add_marker(skip_mysql)
