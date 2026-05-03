"""Top-level package for the collusive covert HotpotQA experiment."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _configure_matplotlib_cache() -> None:
    cache_root = Path(tempfile.gettempdir()) / "covert_collusive_hotpot"
    mpl_cache_dir = cache_root / "matplotlib"
    xdg_cache_dir = cache_root / "xdg-cache"
    mpl_cache_dir.mkdir(parents=True, exist_ok=True)
    xdg_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache_dir))


_configure_matplotlib_cache()
