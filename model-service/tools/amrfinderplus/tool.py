"""
AMRFinderPlus (NCBI), with its hits interpreted by AMRrules (AMRverse) where it has rules.

1. AMRFinderPlus looks for known resistance genes and, for the organisms it knows (--organism),
   point mutations, in an assembly (-n: translated search, no annotation needed).
2. For the organisms AMRrules has rules for, AMRrules decides what each hit means for each
   antibiotic or class: e.g. blaEC in E. coli is wildtype (S to cefotaxime). Each of its verdicts
   is a result, with the rules and markers behind it.
3. A hit no rule interprets says what AMRFinderPlus says: its subclass, as an ARO term through the
   table of AMRrules. A subclass that is an antibiotic gives R; one that is a class gives
   "possible", since a gene of a class does not always make a strain resistant to all of it.
4. Every antibiotic or class of that table with no result is "not_detected".

Cocos applies the results about a class to the antibiotics under it in ARO.
"""
import csv
import os
import re
from functools import lru_cache
from pathlib import Path

from registry import InputError, run_in_env

INPUTS = ("assembly",)

NAME = "amrfinderplus"
DB = Path("/opt/amrfinderplus-db/latest")
THREADS = os.getenv("AMRFINDERPLUS_THREADS", "4")

# NCBITaxon CURIE → (organism of AMRFinderPlus --organism, organism of AMRrules), each None if it
# does not know it. Labels checked in OLS (NCBITaxon); see `amrfinder -l` and `amrrules --list-organisms`.
ORGANISMS = {
    "NCBITaxon:470": ("Acinetobacter_baumannii", "s__Acinetobacter baumannii"),
    "NCBITaxon:520": ("Bordetella_pertussis", "s__Bordetella pertussis"),
    "NCBITaxon:292": ("Burkholderia_cepacia", None),
    "NCBITaxon:13373": ("Burkholderia_mallei", None),
    "NCBITaxon:28450": ("Burkholderia_pseudomallei", "s__Burkholderia pseudomallei"),
    "NCBITaxon:194": ("Campylobacter", None),
    "NCBITaxon:197": ("Campylobacter", "s__Campylobacter jejuni"),
    "NCBITaxon:546": ("Citrobacter_freundii", None),
    "NCBITaxon:1496": ("Clostridioides_difficile", None),
    "NCBITaxon:1717": ("Corynebacterium_diphtheriae", None),
    "NCBITaxon:61645": ("Enterobacter_asburiae", None),
    "NCBITaxon:550": ("Enterobacter_cloacae", None),
    "NCBITaxon:158836": ("Enterobacter_cloacae", "s__Enterobacter hormaechei"),  # of the E. cloacae complex
    "NCBITaxon:1351": ("Enterococcus_faecalis", "s__Enterococcus faecalis"),
    "NCBITaxon:1352": ("Enterococcus_faecium", "s__Enterococcus faecium"),
    "NCBITaxon:561": ("Escherichia", None),
    "NCBITaxon:562": ("Escherichia", "s__Escherichia coli"),
    "NCBITaxon:727": ("Haemophilus_influenzae", None),
    "NCBITaxon:210": ("Helicobacter_pylori", None),
    "NCBITaxon:571": ("Klebsiella_oxytoca", "s__Klebsiella oxytoca"),
    "NCBITaxon:573": ("Klebsiella_pneumoniae", "s__Klebsiella pneumoniae"),
    "NCBITaxon:1773": (None, "s__Mycobacterium tuberculosis"),
    "NCBITaxon:485": ("Neisseria_gonorrhoeae", "s__Neisseria gonorrhoeae"),
    "NCBITaxon:487": ("Neisseria_meningitidis", "s__Neisseria meningitidis"),
    "NCBITaxon:287": ("Pseudomonas_aeruginosa", "s__Pseudomonas aeruginosa"),
    "NCBITaxon:590": ("Salmonella", None),
    "NCBITaxon:28901": ("Salmonella", "s__Salmonella enterica"),
    "NCBITaxon:615": ("Serratia_marcescens", None),
    "NCBITaxon:1280": ("Staphylococcus_aureus", "s__Staphylococcus aureus"),
    "NCBITaxon:1282": ("Staphylococcus_epidermidis", None),
    "NCBITaxon:283734": ("Staphylococcus_pseudintermedius", None),
    "NCBITaxon:1311": ("Streptococcus_agalactiae", None),
    "NCBITaxon:1313": ("Streptococcus_pneumoniae", None),
    "NCBITaxon:1314": ("Streptococcus_pyogenes", None),
    "NCBITaxon:666": ("Vibrio_cholerae", None),
    "NCBITaxon:670": ("Vibrio_parahaemolyticus", None),
    "NCBITaxon:672": ("Vibrio_vulnificus", None),
}

# AMRFinderPlus subclasses that are mechanisms, not antibiotics or classes: no result is about them
NOT_DRUGS = {"EFFLUX"}

# The verdicts of AMRrules (its clinical category) as calls; "NS" (non-susceptible) is taken as R
CATEGORIES = {"R": "R", "NS": "R", "I": "I", "S": "S"}


def run(inputs, organism, workdir):
    amrfinder_organism, amrrules_organism = ORGANISMS.get(organism, (None, None))
    hits_file = workdir / "amrfinderplus.tsv"
    command = ["amrfinder", "--database", str(DB), "--nucleotide", str(inputs["assembly"]), "--plus",
               "--print_node", "--threads", THREADS, "--output", str(hits_file)]
    if amrfinder_organism:
        command += ["--organism", amrfinder_organism]
    done = run_in_env(NAME, command, cwd=workdir)
    if done.returncode != 0:
        message = _last_lines(done.stderr)
        # AMRFinderPlus checks the FASTA it is given before searching it
        if re.search(r"fasta|sequence|nucleotide", message, re.IGNORECASE):
            raise InputError(f"AMRFinderPlus could not read the assembly: {message}")
        raise RuntimeError(f"AMRFinderPlus failed: {message}")

    hits = [hit for hit in _read_tsv(hits_file) if hit["Type"] == "AMR"]
    by_gene = {hit["Element symbol"]: hit for hit in hits}
    results, interpreted = [], set()
    if amrrules_organism and hits:
        results, interpreted = _interpret(hits_file, amrrules_organism, workdir, by_gene)
    results += _by_subclass([hit for hit in hits if hit["Element symbol"] not in interpreted])
    found = {result["about"] for result in results}
    results += [{"about": term, "call": "not_detected"} for term in sorted(set(_subclasses().values()) - found)]
    return results, hits_file


def _interpret(hits_file, organism, workdir, by_gene):
    """(results, genes interpreted by a rule): the verdicts of AMRrules, from its genome summary."""
    done = run_in_env(NAME, ["amrrules", "--input", str(hits_file), "--organism", organism,
                             "--output-prefix", "amrrules", "--output-dir", str(workdir)], cwd=workdir)
    if done.returncode != 0:
        raise RuntimeError(f"AMRrules failed: {_last_lines(done.stderr or done.stdout)}")
    terms = _aro_terms()
    results, interpreted = [], set()
    for row in _read_tsv(workdir / "amrrules_genome_summary.tsv"):
        call = CATEGORIES.get(row["clinical category"])
        drug = row["drug"] if row["drug"] not in ("(all)", "(n/a)", "-") else row["drug class"]
        about = terms.get(drug.strip().lower())
        if call is None or about is None:
            continue
        markers = {"non-S": _markers(row["markers (non-S)"]), "S": _markers(row["markers (S)"])}
        interpreted |= markers["non-S"] | markers["S"]
        rules = row["ruleIDs"].split(";") if row["ruleIDs"] not in ("", "-") else []
        evidence = [{**_hit_evidence(by_gene.get(gene), gene), "effect": "non-S" if gene in markers["non-S"] else "S",
                     "rules": rules, "evidence_grade": row["evidence grade"], "source": "AMRrules"}
                    for gene in sorted(markers["non-S"] | markers["S"])]
        results.append({"about": about, "call": call, "evidence": evidence})
    return results, interpreted


def _by_subclass(hits):
    """Results of the hits no rule interprets, from their subclass: R about an antibiotic, "possible"
    about a class; with every hit of each term as evidence."""
    subclasses, terms = _subclasses(), _drug_terms()
    found = {}
    for hit in hits:
        for subclass in hit["Subclass"].split("/"):
            about = subclasses.get(subclass.strip())
            if about:
                found.setdefault(about, []).append({**_hit_evidence(hit), "subclass": subclass.strip(),
                                                    "source": "AMRFinderPlus"})
    return [{"about": about, "call": "R" if about in terms else "possible", "evidence": evidence}
            for about, evidence in sorted(found.items())]


def _hit_evidence(hit, gene=None):
    """What a piece of evidence says about a hit of AMRFinderPlus (or only its gene, if not given)."""
    if hit is None:
        return {"gene": gene}
    evidence = {
        "gene": hit["Element symbol"],
        "name": hit["Element name"],
        "method": hit["Method"],
        "identity": _number(hit["% Identity to reference"]),
        "coverage": _number(hit["% Coverage of reference"]),
        "accession": hit["Closest reference accession"],
        "node": hit.get("Hierarchy node", ""),
        "contig": hit["Contig id"],
    }
    return {key: value for key, value in evidence.items() if value not in (None, "", "NA")}


def _markers(text):
    """The genes of a list of markers of AMRrules: 'blaEC-5;gyrA_S83L' → {'blaEC-5', 'gyrA_S83L'}."""
    return {marker.strip() for marker in text.split(";") if marker.strip() not in ("", "-")}


def _number(text):
    try:
        return float(text)
    except ValueError:
        return None


def _read_tsv(path):
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file, delimiter="\t"))


def _last_lines(text, count=3):
    return " ".join(line.strip() for line in (text or "").strip().splitlines()[-count:])


# --- Resources of AMRrules: its table of subclasses, and the ARO (aro.obo of CARD) it uses

@lru_cache(maxsize=None)
def _resources():
    done = run_in_env(NAME, ["python", "-c", "import amrrules, pathlib; print(pathlib.Path(amrrules.__file__).parent / 'resources')"],
                      cwd="/tmp")
    return Path(done.stdout.strip().splitlines()[-1])


@lru_cache(maxsize=None)
def _subclasses():
    """{subclass of AMRFinderPlus: its ARO term}, from the table of AMRrules (but the mechanisms)."""
    return {row["AFP_Subclass"].strip(): row["CARD ARO"].strip()
            for row in _read_tsv(_resources() / "amrfp_to_card_drugs_classes.txt")
            if row["CARD ARO"].strip().startswith("ARO:") and row["AFP_Subclass"].strip() not in NOT_DRUGS}


@lru_cache(maxsize=None)
def _drug_terms():
    """The terms of that table that are antibiotics (it names a drug), not classes."""
    return {row["CARD ARO"].strip() for row in _read_tsv(_resources() / "amrfp_to_card_drugs_classes.txt")
            if row["CARD drug"].strip() not in ("", "-")}


@lru_cache(maxsize=None)
def _aro_terms():
    """{name in lower case: ARO id} of the terms of aro.obo, the names AMRrules uses for drugs and classes."""
    terms, term_id = {}, None
    with open(_resources() / "aro.obo", encoding="utf-8") as obo:
        for line in obo:
            if line.startswith("id: ARO:"):
                term_id = line[4:].strip()
            elif line.startswith("name: ") and term_id:
                terms[line[6:].strip().lower()] = term_id
                term_id = None
    return terms


# --- Versions

@lru_cache(maxsize=None)
def software():
    done = run_in_env(NAME, ["amrfinder", "--version"], cwd="/tmp")
    amrfinder = done.stdout.strip().splitlines()[-1] if done.returncode == 0 else ""
    database = (DB / "version.txt").read_text(encoding="utf-8").strip() if (DB / "version.txt").exists() else ""
    done = run_in_env(NAME, ["amrrules", "--version"], cwd="/tmp")
    amrrules = done.stdout.strip().split()[-1] if done.returncode == 0 else ""
    return [
        {"name": "AMRFinderPlus", "version": amrfinder, "type": "tool", "biotools": "amrfinderplus"},
        {"name": "AMRFinderPlus database", "version": database, "type": "database"},
        {"name": "AMRrules", "version": amrrules, "type": "tool"},
    ]
