import pytest


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """No test reads or changes the user's settings, or registers the app to start with Windows."""
    monkeypatch.setenv("FLBP_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("FLBP_NO_STARTUP", "1")
