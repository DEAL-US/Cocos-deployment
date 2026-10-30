"""A fake tool for the tests: a verdict with its evidence and a probability, from an assembly."""
from registry import InputError

INPUTS = ("assembly",)


def run(inputs, organism, workdir):
    assembly = inputs["assembly"].read_text()
    if not assembly.startswith(">"):
        raise InputError("The assembly is not a FASTA file")
    raw = workdir / "fake_output.tsv"
    raw.write_text(f"gene\torganism\nblaFAKE-1\t{organism}\n")
    return [
        {"about": "ARO:0000020", "call": "R", "evidence": [{"gene": "blaFAKE-1", "identity": 99.5}]},
        {"about": "ARO:0000013", "score": 0.25},
    ], raw


def software():
    return [{"name": "Fake", "version": "1.0", "type": "tool"}]
