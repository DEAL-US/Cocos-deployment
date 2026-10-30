"""The tests run the service with the fake tools of tests/tools, an in-memory Redis and jobs run at once."""
import fnmatch
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SERVICE = Path(__file__).parent.parent
os.environ["TOOLS_DIR"] = str(Path(__file__).parent / "tools")
sys.path.insert(0, str(SERVICE))

import jobs  # noqa: E402
import tasks  # noqa: E402


class FakeRedis:
    """The few Redis commands jobs.py uses, in memory."""

    def __init__(self):
        self.data = {}

    def set(self, key, value, ex=None):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)

    def scan_iter(self, pattern):
        return [key for key in list(self.data) if fnmatch.fnmatch(key, pattern)]


@pytest.fixture(autouse=True)
def service(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, "_redis", FakeRedis())
    monkeypatch.setattr(tasks, "WORKDIR", tmp_path)
    import app
    monkeypatch.setattr(app, "WORKDIR", tmp_path)
    monkeypatch.setattr(app, "predict", SimpleNamespace(delay=tasks.predict))  # run the job at once
    return app
