"""Central path resolution shared by all packages.

Resolution order for the repository root:

1. ``MINING_BRIEF_HOME`` environment variable (used by Docker and by tests
   that point at a fixture tree).
2. The nearest ancestor directory of this file that contains
   ``pyproject.toml`` (works for editable installs from a checkout).
3. ``Path.cwd()`` as a last resort (works when the process is started from
   the repository root, e.g. ``WORKDIR /app`` in the Docker image).
"""

from __future__ import annotations

import os
from pathlib import Path

HOME_ENV_VAR = "MINING_BRIEF_HOME"


def project_root() -> Path:
    """Return the repository root directory."""
    override = os.environ.get(HOME_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()

    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd()


def data_dir() -> Path:
    return project_root() / "data"


def snapshots_dir() -> Path:
    return data_dir() / "snapshots"


def prices_snapshot_dir() -> Path:
    return snapshots_dir() / "prices"


def samples_dir() -> Path:
    return data_dir() / "samples"


def projects_file() -> Path:
    return data_dir() / "projects.json"


def cache_dir() -> Path:
    """Return (and create) the runtime cache directory for downloaded files."""
    directory = data_dir() / "cache"
    directory.mkdir(parents=True, exist_ok=True)
    return directory
