"""The AMRFinderPlus tool, with the outputs of AMRFinderPlus and AMRrules on E. coli ATCC 25922 (a
susceptible strain) instead of running them. Needs the image: it reads the resources of AMRrules."""
import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

from registry import InputError
from results import check_results

SERVICE = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures" / "amrfinderplus"

spec = importlib.util.spec_from_file_location("amrfinderplus_tool", SERVICE / "tools" / "amrfinderplus" / "tool.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

CEFOTAXIME, THIRD_GENERATION_CEPHALOSPORIN, AMIKACIN = "ARO:3000645", "ARO:0000032", "ARO:0000013"

# A hit of an acquired gene whose subclasses are antibiotics, added to the hits of ATCC 25922
AAC6 = ["NA", "1", "100", "700", "+", "aac(6')-Ib", "aminoglycoside 6'-N-acetyltransferase AAC(6')-Ib", "core", "AMR",
        "AMR", "AMINOGLYCOSIDE", "AMIKACIN/KANAMYCIN/TOBRAMYCIN", "EXACTX", "200", "200", "100.00", "100.00", "200",
        "WP_000000001.1", "AAC(6')-Ib", "NA", "NA", "aac(6')-Ib"]


def fake_tools(hits, calls):
    """A run_in_env that writes `hits` as the output of AMRFinderPlus and the summary of ATCC 25922 as
    that of AMRrules, recording the commands, and runs anything else (e.g. the version of a tool)."""
    def run_in_env(name, command, cwd, timeout=None):
        calls.append(command)
        if command[0] == "amrfinder" and "--output" in command:
            Path(command[command.index("--output") + 1]).write_text(hits, encoding="utf-8")
        elif command[0] == "amrrules" and "--input" in command:
            shutil.copy(FIXTURES / "ATCC25922_amrrules_genome_summary.tsv", Path(cwd) / "amrrules_genome_summary.tsv")
        else:
            return subprocess.run(["conda", "run", "-n", f"tool_{name}", *command], cwd=cwd, capture_output=True, text=True)
        return subprocess.CompletedProcess(command, 0, "", "")
    return run_in_env


def run(monkeypatch, tmp_path, organism, hits=None):
    calls = []
    hits = hits or (FIXTURES / "ATCC25922_amrfinderplus.tsv").read_text(encoding="utf-8")
    monkeypatch.setattr(tool, "run_in_env", fake_tools(hits, calls))
    results, raw = tool.run({"assembly": tmp_path / "sample.fasta"}, organism, tmp_path)
    return {result["about"]: result for result in check_results(results)}, raw, calls


def test_amrrules_interprets_the_hits_of_an_organism_it_has_rules_for(monkeypatch, tmp_path):
    results, raw, calls = run(monkeypatch, tmp_path, "NCBITaxon:562")

    assert "--organism" in calls[0] and calls[0][calls[0].index("--organism") + 1] == "Escherichia"
    assert calls[1][calls[1].index("--organism") + 1] == "s__Escherichia coli"
    cefotaxime = results[CEFOTAXIME]
    assert cefotaxime["call"] == "S"  # blaEC is wildtype in E. coli, not a resistance
    [evidence] = cefotaxime["evidence"]
    assert (evidence["gene"], evidence["effect"], evidence["rules"], evidence["source"]) == \
        ("blaEC-5", "S", ["ECO0011", "ECO0012"], "AMRrules")
    assert evidence["identity"] == 100.0 and evidence["accession"]
    assert raw.name == "amrfinderplus.tsv"


def test_without_rules_a_gene_of_a_class_is_a_possible_resistance(monkeypatch, tmp_path):
    results, _, calls = run(monkeypatch, tmp_path, None)

    assert "--organism" not in calls[0] and len(calls) == 1  # no organism: neither -O nor AMRrules
    cephalosporin = results[THIRD_GENERATION_CEPHALOSPORIN]
    assert cephalosporin["call"] == "possible"
    assert [(item["gene"], item["subclass"], item["source"]) for item in cephalosporin["evidence"]] == \
        [("blaEC-5", "CEPHALOSPORIN", "AMRFinderPlus")]


def test_without_rules_a_gene_of_an_antibiotic_is_a_resistance(monkeypatch, tmp_path):
    hits = (FIXTURES / "ATCC25922_amrfinderplus.tsv").read_text(encoding="utf-8") + "\t".join(AAC6) + "\n"
    results, _, _ = run(monkeypatch, tmp_path, None, hits)

    assert results[AMIKACIN]["call"] == "R"
    assert results[AMIKACIN]["evidence"][0]["gene"] == "aac(6')-Ib"


def test_what_is_not_found_is_not_detected_and_mechanisms_are_left_out(monkeypatch, tmp_path):
    results, _, _ = run(monkeypatch, tmp_path, None)

    assert results[AMIKACIN] == {"about": AMIKACIN, "call": "not_detected"}
    assert "ARO:0010000" not in results  # antibiotic efflux: a mechanism, not an antibiotic


def test_an_unreadable_assembly_is_an_input_error(monkeypatch, tmp_path):
    def run_in_env(name, command, cwd, timeout=None):
        return subprocess.CompletedProcess(command, 1, "", "Error: sample.fasta is not a nucleotide FASTA file")
    monkeypatch.setattr(tool, "run_in_env", run_in_env)

    with pytest.raises(InputError, match="could not read the assembly"):
        tool.run({"assembly": tmp_path / "sample.fasta"}, None, tmp_path)


def test_software_has_the_versions_of_the_tools_and_the_database():
    names = [entry["name"] for entry in tool.software()]
    assert names == ["AMRFinderPlus", "AMRFinderPlus database", "AMRrules"]
    assert all(entry["version"] for entry in tool.software())
