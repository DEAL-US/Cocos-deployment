#!/bin/sh
# Runs once, in the environment of the tool, when the image is built (see the Dockerfile).
# Installs AMRrules and downloads the AMRFinderPlus database into the image, so that its version is
# fixed with the image, and the resources of AMRrules: the CARD files it needs and the gene
# hierarchy of that same database version (AMRrules would otherwise download the latest one).
set -e

# AMRrules is not on PyPI or bioconda: its rules are copied into the package before installing it,
# and its resources folder (with its table of AMRFinderPlus subclasses to CARD) is not installed
AMRRULES_VERSION=v1.0.1
git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$AMRRULES_VERSION" https://github.com/AMRverse/AMRrules.git /tmp/amrrules
(cd /tmp/amrrules && python copy_rules.py && pip install --no-deps --quiet .)
RESOURCES=$(python -c "import amrrules, pathlib; print(pathlib.Path(amrrules.__file__).parent / 'resources')")
mkdir -p "$RESOURCES"
cp /tmp/amrrules/src/amrrules/resources/* "$RESOURCES/"
rm -rf /tmp/amrrules

DB=/opt/amrfinderplus-db
amrfinder_update --database "$DB"
VERSION=$(cat "$DB/latest/version.txt")

amrrules --download-resources
MAJOR=$(amrfinder --version | cut -d. -f1,2)
BASE="https://ftp.ncbi.nlm.nih.gov/pathogen/Antimicrobial_resistance/AMRFinderPlus/database/$MAJOR/$VERSION"
python - "$BASE" "$RESOURCES" <<'PY'
import sys, urllib.request
base, resources = sys.argv[1], sys.argv[2]
for name in ("ReferenceGeneHierarchy.txt", "version.txt"):
    with urllib.request.urlopen(f"{base}/{name}") as response, open(f"{resources}/{name}", "wb") as target:
        target.write(response.read())
PY
echo "AMRFinderPlus database $VERSION, with its gene hierarchy for AMRrules $AMRRULES_VERSION"
