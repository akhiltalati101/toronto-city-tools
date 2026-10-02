"""Loads one of the sibling apps' `app.py` into the hub process, fresh, on
every activation.

Each app dir (area-scorecard/, city-scorecard/, ev-scorecard/) has its own
geocode.py, mapview.py, pipeline.py, etc., all imported with bare names
(`from mapview import ...`). Python caches imports by bare name in
`sys.modules` process-wide, so if two apps' same-named-but-different modules
both got imported into one long-running hub process, whichever loaded first
would silently "win" that name for every other app's subsequent import —
wrong logic executing for a page. To avoid that, purge this app's own
filenames from `sys.modules` and re-import `app.py` fresh immediately before
rendering it; other apps' pages don't get invoked (an `st.Page` callable
only runs while that page is active), so their modules are never present to
collide with in the first place.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent

# All sibling app dirs, so a stale one can be scrubbed from sys.path before
# each render — otherwise, once two apps have each been visited once, both
# of their directories sit on sys.path permanently, and Python resolves a
# bare `import mapview` to whichever app dir comes first, not necessarily
# the one currently being rendered (confirmed by testing: after
# area -> city -> ev -> area, the last "area" run silently imported ev's
# mapview.py, since ev's directory had been inserted at index 0 last).
_SIBLING_APP_DIRS = [
    str(p.parent) for p in REPO_ROOT.glob("*/app.py") if p.parent.name != "hub"
]


def load_app_page(app_dir_name: str) -> Callable[[], None]:
    """Return a zero-arg callable suitable for `st.Page(...)` that (re)loads
    `<app_dir_name>/app.py` and calls its `render()`.
    """
    app_dir = REPO_ROOT / app_dir_name
    local_module_names = {p.stem for p in app_dir.glob("*.py")}

    def _render() -> None:
        for name in local_module_names:
            sys.modules.pop(name, None)

        for sibling in _SIBLING_APP_DIRS:
            if sibling in sys.path:
                sys.path.remove(sibling)
        sys.path.insert(0, str(app_dir))

        module_key = f"_hub_{app_dir_name.replace('-', '_')}_app"
        spec = importlib.util.spec_from_file_location(module_key, app_dir / "app.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_key] = module
        spec.loader.exec_module(module)
        module.render()

    return _render
