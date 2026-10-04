"""
This file MUST set NUKKAD_DATABASE_URL before any `app.*` module is
imported, because app.core.config.Settings is built once at import time.
pytest imports conftest.py before collecting test modules in the same
directory, so setting the environment variable here (at module scope, not
inside a fixture) is early enough.
"""
from __future__ import annotations

import os
import tempfile

_tmp_dir = tempfile.mkdtemp(prefix="nukkad_test_")
os.environ["NUKKAD_DATABASE_URL"] = f"sqlite:///{_tmp_dir}/test_nukkad.db"
os.environ.setdefault("NUKKAD_DAILY_CREDIT_CAP", "10000")
os.environ.setdefault("SERPAPI_API_KEY", "test-serpapi-key")

from app.db.database import init_db  # noqa: E402

init_db()
