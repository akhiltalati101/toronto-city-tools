"""Puts the repo root on sys.path (for `common`) and loads app modules by
file path. App dirs reuse bare module names (geocode, pipeline, ...), so
they're imported under unique names rather than by adding the app dirs
to sys.path — see common/app_loader.py for the same problem in the hub.
"""
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def load_app_module(app_dir: str, name: str):
    key = f"_test_{app_dir.replace('-', '_')}_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, REPO_ROOT / app_dir / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module
