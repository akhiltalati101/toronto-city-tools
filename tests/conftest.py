"""Puts the repo root on sys.path (for `toronto_tools` and `api`) and this
directory on it (for `overpass_fixtures`), so tests run without installing
the package."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
