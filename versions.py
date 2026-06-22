import os
import json
from datetime import datetime

import requests

from scraper import load_json, save_json

# Version storage
# ---------------
# Each scrape of an exam is stored as a full snapshot. Version 1 keeps the
# original, un-suffixed filename so every exam scraped before versioning
# existed is treated as version 1 ("no version means version 1"). Newer
# re-scrapes are written alongside it as ``{code}_v{n}.json``.

DATA_DIR = "data"
GITHUB_RAW = (
    "https://raw.githubusercontent.com/17Andri17/"
    "ExamTopics-Question-Viewer/refs/heads/main/data/"
)


def base_path(exam_code):
    return os.path.join(DATA_DIR, f"{exam_code}.json")


def version_path(exam_code, version):
    if version and version > 1:
        return os.path.join(DATA_DIR, f"{exam_code}_v{version}.json")
    return base_path(exam_code)


def links_path(exam_code, version):
    if version and version > 1:
        return os.path.join(DATA_DIR, f"{exam_code}_v{version}_links.json")
    return os.path.join(DATA_DIR, f"{exam_code}_links.json")


def local_versions(exam_code):
    """Return the sorted list of version numbers present on disk."""
    versions = []
    if os.path.exists(base_path(exam_code)):
        versions.append(1)
    n = 2
    while os.path.exists(version_path(exam_code, n)):
        versions.append(n)
        n += 1
    return versions


def next_version(exam_code):
    """Version number a re-scrape should write to.

    Continues an unfinished latest version if one exists, otherwise starts a
    fresh version after the newest complete one.
    """
    versions = local_versions(exam_code)
    if not versions:
        return 1
    latest = max(versions)
    obj = load_json(version_path(exam_code, latest))
    if obj.get("status") == "complete":
        return latest + 1
    return latest


def version_label(exam_code, version, latest):
    """Human-friendly label for the version selector."""
    label = f"Version {version}" + (" (latest)" if version == latest else "")
    path = version_path(exam_code, version)
    if os.path.exists(path):
        try:
            ts = datetime.fromtimestamp(os.path.getmtime(path))
            label += f" — {ts:%Y-%m-%d}"
        except OSError:
            pass
    return label


def stamp_version(exam_code, version):
    """Record when a version was scraped, inside its snapshot file."""
    path = version_path(exam_code, version)
    obj = load_json(path)
    if not obj:
        return
    obj.setdefault("scraped_at", datetime.now().isoformat(timespec="seconds"))
    obj["version"] = version
    save_json(obj, path)


# --- Deployed (read-only) GitHub helpers ---------------------------------

def _github_filename(exam_code, version):
    if version and version > 1:
        return f"{exam_code}_v{version}.json"
    return f"{exam_code}.json"


def _github_url(exam_code, version):
    return GITHUB_RAW + requests.utils.quote(_github_filename(exam_code, version))


def github_versions(exam_code, max_probe=50):
    """Discover which versions exist on GitHub (for the deployed app)."""
    versions = []
    version = 1
    while version <= max_probe:
        try:
            resp = requests.head(_github_url(exam_code, version), timeout=10)
            if resp.status_code == 405:  # HEAD not allowed; fall back to GET
                resp = requests.get(_github_url(exam_code, version), timeout=10, stream=True)
        except requests.RequestException:
            break
        if resp.status_code != 200:
            break
        versions.append(version)
        version += 1
    return versions


def load_from_github(exam_code, version=1):
    """Load a specific version's questions from GitHub."""
    try:
        resp = requests.get(_github_url(exam_code, version), timeout=15)
        resp.raise_for_status()
        obj = json.loads(resp.text)
        return obj.get("questions", []), ""
    except requests.RequestException:
        return [], (
            f"Failed to load version {version} for exam {exam_code} from GitHub. "
            "It probably does not exist."
        )
