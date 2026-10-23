"""
Versions of the tools and databases of this service.

Each job records the software it used (see tasks.py), and GET /tools reports what is installed,
so that a client can show which versions will be used and keep which ones were used.

Every entry is a dict:
    {"name": "SPAdes", "version": "4.3.0", "type": "tool", "biotools": "spades"}
    {"name": "Bakta database", "version": "6.0", "type": "database", "variant": "light",
     "date": "2025-02-24", "doi": "10.5281/zenodo.14916843"}

Tools are identified by their bio.tools id and databases by their DOI, when they have one.
The versions of the programs are read once per process (they do not change while the container
runs); the versions of the databases are read every time, since the AMRFinderPlus database can
be updated when a worker starts.
"""
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

BAKTA_DB = Path("/data/bakta_db")

# name -> (display name, command, bio.tools id)
TOOLS = {
    "spades": ("SPAdes", ["spades.py", "--version"], "spades"),
    "raven": ("Raven", ["raven", "--version"], "raven"),
    "flye": ("Flye", ["flye", "--version"], "flye"),
    "bakta": ("Bakta", ["bakta", "--version"], "bakta"),
    "amrfinderplus": ("AMRFinderPlus", ["amrfinder", "--version"], "amrfinderplus"),
}

VERSION_PATTERN = re.compile(r"(\d+(?:\.\d+)+)")


@lru_cache(maxsize=None)
def tool(name):
    """The entry of an installed tool, or None if it is not installed."""
    display_name, command, biotools = TOOLS[name]
    try:
        output = subprocess.run(command, capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = VERSION_PATTERN.search(output)
    if not match:
        return None
    return {"name": display_name, "version": match.group(1), "type": "tool", "biotools": biotools}


def bakta_database():
    """The entry of the Bakta database, from its version.json, or None if it is not there."""
    try:
        info = json.loads((BAKTA_DB / "version.json").read_text())
    except (OSError, ValueError):
        return None
    entry = {
        "name": "Bakta database",
        "version": f"{info['major']}.{info['minor']}",
        "type": "database",
        "variant": info.get("type", ""),
        "date": info.get("date", ""),
    }
    if info.get("doi"):
        entry["doi"] = info["doi"]
    return entry


def amrfinderplus_database():
    """The entry of the AMRFinderPlus database that Bakta uses, or None if it is not there."""
    try:
        version = (BAKTA_DB / "amrfinderplus-db" / "latest" / "version.txt").read_text().strip()
    except OSError:
        return None
    return {"name": "AMRFinderPlus database", "version": version, "type": "database"}


def assembly_software(assembler):
    """What an assembly with `assembler` ('spades', 'raven' or 'flye') uses."""
    return _present([tool(assembler)])


def annotation_software():
    """What an annotation uses: Bakta and its database, and AMRFinderPlus (which Bakta runs) and its database."""
    return _present([tool("bakta"), bakta_database(), tool("amrfinderplus"), amrfinderplus_database()])


def installed():
    """Everything this service has, for GET /tools."""
    return {
        "assembly": {
            "illumina": assembly_software("spades"),
            "ont": _present([tool("flye") or tool("raven")]),
        },
        "annotation": annotation_software(),
    }


def _present(entries):
    return [entry for entry in entries if entry is not None]
