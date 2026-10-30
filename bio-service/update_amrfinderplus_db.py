"""
Update the AMRFinderPlus database inside the Bakta database, if there is a new version. The worker
runs it when it starts.

amrfinder_update downloads the new version and indexes it (makeblastdb). On Docker Desktop for
Windows, that indexing fails with an LMDB error on the mounted folder, so the version is then indexed
in a copy inside the container and the index is copied back.
"""
import shutil
import subprocess
import sys
from pathlib import Path

from versions import BAKTA_DB

AMRFINDERPLUS_DB = BAKTA_DB / "amrfinderplus-db"
INDEX_COPY = Path("/tmp/amrfinderplus-db")


def main():
    if subprocess.run(["amrfinder_update", "--database", f"{AMRFINDERPLUS_DB}/"]).returncode == 0:
        return 0
    latest = AMRFINDERPLUS_DB / "latest"
    if not latest.is_symlink():  # nothing was downloaded
        return 1
    version = latest.resolve()
    print(f"Indexing the AMRFinderPlus database {version.name} again, inside the container")
    shutil.rmtree(INDEX_COPY, ignore_errors=True)
    shutil.copytree(version, INDEX_COPY)
    if subprocess.run(["amrfinder_index", f"{INDEX_COPY}/"]).returncode != 0:
        return 1
    shutil.copytree(INDEX_COPY, version, dirs_exist_ok=True)
    shutil.rmtree(INDEX_COPY)
    return 0


if __name__ == "__main__":
    sys.exit(main())
