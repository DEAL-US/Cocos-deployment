# The software the real service reports (docker-servicios-bio/versions.py), with the versions it pins
ASSEMBLERS = {
    "illumina": {"spades": [{"name": "SPAdes", "version": "4.3.0", "type": "tool", "biotools": "spades"}]},
    "ont": {
        "raven": [{"name": "Raven", "version": "1.8.3", "type": "tool", "biotools": "raven"}],
        "flye": [{"name": "Flye", "version": "2.9.6", "type": "tool", "biotools": "flye"}],
    },
}
DEFAULT_ASSEMBLERS = {"illumina": "spades", "ont": "raven"}
ASSEMBLY_SOFTWARE = {technology: ASSEMBLERS[technology][default] for technology, default in DEFAULT_ASSEMBLERS.items()}
ANNOTATION_SOFTWARE = [
    {"name": "Bakta", "version": "1.12.1", "type": "tool", "biotools": "bakta"},
    {"name": "Bakta database", "version": "6.0", "type": "database", "variant": "light",
     "date": "2025-02-24", "doi": "10.5281/zenodo.14916843"},
    {"name": "AMRFinderPlus", "version": "4.2.7", "type": "tool", "biotools": "amrfinderplus"},
    {"name": "AMRFinderPlus database", "version": "2026-08-07.1", "type": "database"},
]


def assembly_software(technology: str, annotate: bool, assembler: str | None = None) -> list:
    tools = ASSEMBLERS[technology][assembler or DEFAULT_ASSEMBLERS[technology]]
    return tools + (ANNOTATION_SOFTWARE if annotate else [])


def assemblers() -> dict:
    """The "assemblers" of GET /tools: the default and every assembler, by technology."""
    return {technology: {"default": DEFAULT_ASSEMBLERS[technology], "available": available}
            for technology, available in ASSEMBLERS.items()}


def assembly_fasta() -> bytes:
    return b">mock_contig_1\nATCGATCGATCGATCGATCGATCG\n"


def _feature(locus, start, stop, gene, product, db_xrefs):
    return {
        "type": "cds",
        "sequence": "mock_contig_1",
        "start": start,
        "stop": stop,
        "strand": "+",
        "frame": 1,
        "gene": gene,
        "product": product,
        "db_xrefs": db_xrefs,
        "locus": locus,
        "nt": "ATGAAAAAACTGCTGTAA",
        "aa": "MKKLL",
    }


def annotation_json() -> dict:
    """A small annotation in the Bakta JSON format (only the fields Cocos reads are meaningful)."""
    return {
        "genome": {"genus": "Escherichia", "species": "coli", "strain": "mock"},
        "stats": {"no_sequences": 1, "size": 24},
        "features": [
            _feature("MOCK_00001", 1, 861, "blaTEM-1", "class A broad-spectrum beta-lactamase TEM-1",
                     ["SO:0001217", "UniRef:UniRef50_P62593"]),
            _feature("MOCK_00002", 900, 2075, "tet(A)", "tetracycline efflux MFS transporter Tet(A)",
                     ["SO:0001217", "UniRef:UniRef50_P02982"]),
            _feature("MOCK_00003", 2100, 2915, "aph(3')-Ia", "aminoglycoside O-phosphotransferase APH(3')-Ia",
                     ["SO:0001217", "UniRef:UniRef50_P00551"]),
            _feature("MOCK_00004", 3000, 4299, "kgtP", "alpha-ketoglutarate permease",
                     ["SO:0001217", "UniRef:UniRef50_B2TYL0"]),
        ],
        "sequences": [{"id": "mock_contig_1", "nt": "ATCGATCGATCGATCGATCGATCG", "length": 24}],
        "run": {"start": "2026-01-01 00:00:00", "end": "2026-01-01 00:00:01"},
        "version": {"bakta": "mock", "db": {"version": "mock", "type": "light"}},
    }


def prediction_csv() -> bytes:
    return (
        b"antibiotic,prediction\n"
        b"ampicillin,resistant\n"
        b"ciprofloxacin,sensitive\n"
        b"tetracycline,resistant\n"
    )


def invalid_json() -> dict:
    return {
        "this": "is not a valid annotation result"
    }