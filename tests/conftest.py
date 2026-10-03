import os

import pytest


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """No test reads or changes the user's settings, or registers the app to start with Windows."""
    monkeypatch.setenv("FLBP_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("FLBP_NO_STARTUP", "1")


@pytest.fixture(scope="session")
def application():
    """Qt, drawing off screen: no window or icon shows while the tests run."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
