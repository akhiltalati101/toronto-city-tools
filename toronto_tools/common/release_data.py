"""Downloads the prebuilt datasets that scripts/build_*.py publish as GitHub
Release assets (rebuilt on a schedule by .github/workflows/rebuild-*.yml),
each under a fixed release tag ("city-data", "ev-data", "zoning-data").

Files are cached on local disk under DATA_CACHE_DIR (default: .data_cache/ at
the repo root), so a restarted API process doesn't re-download them. Point
DATA_CACHE_DIR at a persistent volume in production.
"""
import os
from pathlib import Path

import requests

RELEASE_BASE_URL = "https://github.com/akhiltalati101/toronto-city-tools/releases/download"
CACHE_DIR = Path(os.environ.get("DATA_CACHE_DIR", Path(__file__).resolve().parents[2] / ".data_cache"))


def asset_url(release_tag: str, asset_name: str) -> str:
    return f"{RELEASE_BASE_URL}/{release_tag}/{asset_name}"


def download(release_tag: str, asset_name: str) -> Path:
    """Return the local path of a release asset, downloading it on first use."""
    dest = CACHE_DIR / asset_name
    if dest.exists():
        return dest

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(asset_url(release_tag, asset_name), stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    return dest
