"""
Starts FL Studio Better Presence from its sources, and is the entry point of the .exe:

    .venv\\Scripts\\pythonw run.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from flbp.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
